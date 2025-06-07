from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import List, Optional
from pydantic import BaseModel
from utils.google_docs import GoogleDocsManager
from enum import Enum
from fastapi.responses import FileResponse
import os
import sqlite3
import json
from fastapi.responses import Response
import traceback
from utils.supabase_document_ops import SupabaseDocumentOps
import asyncio
from asyncio import TimeoutError
from auth.auth_api import get_user_from_token

# Define the security scheme
security = HTTPBearer()

router = APIRouter(
    prefix="/google-docs",
    tags=["google-docs"]
)

class DocumentStatus(str, Enum):
    CASE_REVIEW_PENDING = "CASE_REVIEW_PENDING"
    CASE_REVIEW_IN_PROGRESS = "CASE_REVIEW_IN_PROGRESS"
    CASE_REVIEW_COMPLETE = "CASE_REVIEW_COMPLETE"
    DATA_REVIEW_IN_PROGRESS = "DATA_REVIEW_IN_PROGRESS"
    PUBLISHED = "PUBLISHED"

class GoogleDocFile(BaseModel):
    id: str
    name: str
    webViewLink: str
    createdTime: str
    modifiedTime: str
    commentCount: int = 0
    status: DocumentStatus = DocumentStatus.CASE_REVIEW_PENDING
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
    approved_by_email: Optional[str] = None
    approved_by_username: Optional[str] = None

class CommentAuthor(BaseModel):
    displayName: str
    email: Optional[str] = None
    photoLink: Optional[str] = None

class CommentModel(BaseModel):
    id: str
    content: str
    author: CommentAuthor
    createdTime: str
    modifiedTime: str
    resolved: bool
    quotedText: Optional[str] = None

@router.post("/create")
async def create_google_doc(
    doc_data: dict,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Create a new Google Doc.
    """
    print(f"[GOOGLE_DOCS] 📝 Creating new doc with data: {doc_data}")
    
    # Extract token and authenticate the user
    try:
        token = credentials.credentials
        print(f"[DEBUG] Extracted JWT: {token}")
        
        print(f"[GOOGLE_DOCS] 🔐 Authenticating user...")
        user_response = await get_user_from_token(token)
        if not user_response["success"]:
            error_message = user_response.get("error", "Authentication required")
            print(f"[GOOGLE_DOCS] ❌ Authentication failed: {error_message}")
            raise HTTPException(status_code=401, detail=error_message)
        
        user_id = user_response["user"]["id"]
        user_role = user_response["user"].get("role", "")
        
        # Check if user is admin or teacher
        if user_role not in ["admin", "teacher"]:
            print(f"[GOOGLE_DOCS] ❌ Access denied: User role '{user_role}' is not authorized")
            raise HTTPException(status_code=403, detail="Only teachers and admins can create Google Docs")
            
        print(f"[GOOGLE_DOCS] ✅ User authenticated successfully. User ID: {user_id}, Role: {user_role}")
        
        try:
            # Your existing Google Doc creation logic here
            # ... existing code ...
            return {"message": "Google Doc created successfully"}
        except Exception as e:
            print(f"[GOOGLE_DOCS] ❌ Error creating Google Doc: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error creating Google Doc: {str(e)}")
            
    except HTTPException as auth_error:
        print(f"[GOOGLE_DOCS] ❌ HTTP exception during authentication: {str(auth_error)}")
        raise auth_error
    except Exception as auth_error:
        print(f"[GOOGLE_DOCS] ❌ Unexpected error during authentication: {str(auth_error)}")
        raise HTTPException(status_code=401, detail="Authentication failed")

@router.get("/list")
async def list_google_docs(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    List all Google Docs.
    """
    print(f"[GOOGLE_DOCS] 📋 Listing all docs")
    
    # Extract token and authenticate the user
    try:
        token = credentials.credentials
        print(f"[DEBUG] Extracted JWT: {token}")
        
        print(f"[GOOGLE_DOCS] 🔐 Authenticating user...")
        user_response = await get_user_from_token(token)
        if not user_response["success"]:
            error_message = user_response.get("error", "Authentication required")
            print(f"[GOOGLE_DOCS] ❌ Authentication failed: {error_message}")
            raise HTTPException(status_code=401, detail=error_message)
        
        user_id = user_response["user"]["id"]
        print(f"[GOOGLE_DOCS] ✅ User authenticated successfully. User ID: {user_id}")
        
        try:
            # Your existing Google Doc listing logic here
            # ... existing code ...
            return {"message": "Google Docs listed successfully"}
        except Exception as e:
            print(f"[GOOGLE_DOCS] ❌ Error listing Google Docs: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error listing Google Docs: {str(e)}")
            
    except HTTPException as auth_error:
        print(f"[GOOGLE_DOCS] ❌ HTTP exception during authentication: {str(auth_error)}")
        raise auth_error
    except Exception as auth_error:
        print(f"[GOOGLE_DOCS] ❌ Unexpected error during authentication: {str(auth_error)}")
        raise HTTPException(status_code=401, detail="Authentication failed")

@router.get("", response_model=List[GoogleDocFile])
async def list_google_docs(department_id: Optional[str] = None):
    """List all Google Docs in the designated folder with their comment counts"""
    try:
        # Define an async function to wrap the synchronous call
        async def get_files():
            docs_manager = GoogleDocsManager()
            # If list_folder_files is synchronous, run it in a thread pool
            if asyncio.iscoroutinefunction(docs_manager.list_folder_files):
                files = await docs_manager.list_folder_files(department_id=department_id)
            else:
                files = await asyncio.to_thread(docs_manager.list_folder_files, department_id=department_id)
            return files
        
        # Use wait_for which works in all Python versions
        files = await asyncio.wait_for(get_files(), timeout=15)
        return files
            
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504,
            detail="Request timed out after 15 seconds. Please retry."
        )
    except Exception as e:
        traceback_str = traceback.format_exc()
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@router.get("/{doc_id}/comments/count", response_model=dict)
async def get_comment_count(doc_id: str):
    """Get the count of unresolved comments for a specific Google Doc"""
    try:
        docs_manager = GoogleDocsManager()
        comment_count = docs_manager.get_unresolved_comment_count(doc_id)
        return {"documentId": doc_id, "unresolvedCommentCount": comment_count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{doc_id}/comments", response_model=List[CommentModel])
async def get_document_comments(doc_id: str, include_deleted: bool = False):
    """
    Get all unresolved comments for a specific Google Doc
    
    Parameters:
    - doc_id: The ID of the Google Doc
    - include_deleted: If true, includes deleted comments (default: False)
    """
    try:
        docs_manager = GoogleDocsManager()
        comments = docs_manager.get_document_comments(
            doc_id, 
            include_deleted=include_deleted
        )
        return comments
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{doc_id}")
async def delete_google_doc(doc_id: str):
    """Delete a Google Doc and its database record"""
    try:
        # Delete from Google Drive
        docs_manager = GoogleDocsManager()
        docs_manager.delete_doc(doc_id)
        
        # Delete from Supabase
        await SupabaseDocumentOps.delete_document(doc_id)
        
        return {"message": f"Document {doc_id} deleted successfully"}
    except Exception as e:
        traceback_str = traceback.format_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/bulk/delete")
async def delete_multiple_google_docs(doc_ids: List[str]):
    """Delete multiple Google Docs and their database records"""
    try:
        docs_manager = GoogleDocsManager()
        results = {
            "successful_deletions": [],
            "failed_deletions": [],
            "total_requested": len(doc_ids),
            "total_successful": 0,
            "total_failed": 0
        }
        
        for doc_id in doc_ids:
            try:
                # Delete from Google Drive
                docs_manager.delete_doc(doc_id)
                
                # Delete from Supabase
                await SupabaseDocumentOps.delete_document(doc_id)
                
                results["successful_deletions"].append({
                    "doc_id": doc_id,
                    "status": "deleted successfully"
                })
                results["total_successful"] += 1
                
            except Exception as e:
                results["failed_deletions"].append({
                    "doc_id": doc_id,
                    "error": str(e),
                    "status": "failed to delete"
                })
                results["total_failed"] += 1
        
        # Return results with appropriate status code
        if results["total_failed"] == 0:
            return {
                "message": f"All {results['total_successful']} documents deleted successfully",
                "results": results
            }
        elif results["total_successful"] == 0:
            raise HTTPException(
                status_code=500, 
                detail={
                    "message": "All document deletions failed",
                    "results": results
                }
            )
        else:
            return {
                "message": f"Partial success: {results['total_successful']} deleted, {results['total_failed']} failed",
                "results": results
            }
            
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        traceback_str = traceback.format_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{doc_id}/approve")
async def approve_and_download_doc(
    doc_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Download a Google Doc and set its status to CASE_REVIEW_COMPLETE"""
    try:
        # Extract token and authenticate the user
        token = credentials.credentials
        print(f"[DEBUG] Extracted JWT: {token}")
        
        # Update status using Supabase
        doc_details = await SupabaseDocumentOps.approve_document(doc_id, token)
        
        # Get updated document details and download
        docs_manager = GoogleDocsManager()
        file_path = docs_manager.download_doc(doc_id)
        
        # Get Google Drive details for response
        drive_details = docs_manager.drive_service.files().get(
            fileId=doc_id,
            fields="id, name, webViewLink, createdTime, modifiedTime"
        ).execute()
        
        # Format response
        response_doc = {
            "id": doc_id,
            "name": drive_details["name"],
            "webViewLink": drive_details["webViewLink"],
            "createdTime": drive_details["createdTime"],
            "modifiedTime": drive_details["modifiedTime"],
            "status": "CASE_REVIEW_COMPLETE",
            "commentCount": 0  # Required by GoogleDocFile model
        }
        
        # Return both the file and document details
        return {
            "document": GoogleDocFile(**response_doc),
            "message": "Document approved and downloaded successfully"
        }
        
    except Exception as e:
        traceback_str = traceback.format_exc()
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=str(e)) 
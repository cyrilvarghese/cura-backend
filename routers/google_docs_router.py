from fastapi import APIRouter, HTTPException, BackgroundTasks
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

router = APIRouter()

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

@router.get("/google-docs", response_model=List[GoogleDocFile])
async def list_google_docs():
    """List all Google Docs in the designated folder with their comment counts"""
    try:
        print("Starting Google Docs list request...")
        
        # Define an async function to wrap the synchronous call
        async def get_files():
            docs_manager = GoogleDocsManager()
            print("GoogleDocsManager initialized")
            # If list_folder_files is synchronous, run it in a thread pool
            if asyncio.iscoroutinefunction(docs_manager.list_folder_files):
                files = await docs_manager.list_folder_files()
            else:
                files = await asyncio.to_thread(docs_manager.list_folder_files)
            print(f"Retrieved {len(files) if files else 0} files")
            return files
        
        # Use wait_for which works in all Python versions
        files = await asyncio.wait_for(get_files(), timeout=15)
        return files
            
    except asyncio.TimeoutError:
        print("Request timed out after 15 seconds")
        raise HTTPException(
            status_code=504,
            detail="Request timed out after 15 seconds. Please retry."
        )
    except Exception as e:
        print(f"Error type: {type(e).__name__}")
        print(f"Error in list_google_docs: {str(e)}")
        print(f"Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@router.get("/google-docs/{doc_id}/comments/count", response_model=dict)
async def get_comment_count(doc_id: str):
    """Get the count of unresolved comments for a specific Google Doc"""
    try:
        docs_manager = GoogleDocsManager()
        comment_count = docs_manager.get_unresolved_comment_count(doc_id)
        return {"documentId": doc_id, "unresolvedCommentCount": comment_count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/google-docs/{doc_id}/comments", response_model=List[CommentModel])
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

@router.delete("/google-docs/{doc_id}")
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
        print(f"Error in delete_google_doc: {str(e)}")
        print(f"Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/google-docs/{doc_id}/approve")
async def approve_and_download_doc(doc_id: str):
    """Download a Google Doc and set its status to CASE_REVIEW_COMPLETE"""
    try:
        print(f"Starting approval process for doc_id: {doc_id}")
        
        # Update status using Supabase
        doc_details = await SupabaseDocumentOps.approve_document(doc_id)
        
        # Get updated document details and download
        docs_manager = GoogleDocsManager()
        file_path = docs_manager.download_doc(doc_id)
        print(f"File downloaded to: {file_path}")
        
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
        print(f"Error in approve_and_download_doc: {str(e)}")
        print(f"Full traceback: {traceback.format_exc()}")
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=str(e)) 
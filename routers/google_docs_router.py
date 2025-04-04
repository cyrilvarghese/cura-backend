from fastapi import APIRouter, HTTPException
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
        docs_manager = GoogleDocsManager()
        files = docs_manager.list_folder_files()
        return files
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
        docs_manager = GoogleDocsManager()
        docs_manager.delete_doc(doc_id)
        return {"message": f"Document {doc_id} deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/google-docs/{doc_id}/approve")
async def approve_and_download_doc(doc_id: str):
    """Download a Google Doc and set its status to CASE_REVIEW_COMPLETE"""
    try:
        print(f"Starting approval process for doc_id: {doc_id}")
        
        # First update the status
        conn = sqlite3.connect('medical_assessment.db')
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                UPDATE documents 
                SET status = ? 
                WHERE google_doc_id = ?
            ''', (DocumentStatus.CASE_REVIEW_COMPLETE.value, doc_id))
            
            if cursor.rowcount == 0:
                print(f"No document found in database with google_doc_id: {doc_id}")
                conn.close()
                raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")
            
            conn.commit()
            print(f"Successfully updated status for doc_id: {doc_id}")
            
        except sqlite3.Error as db_error:
            print(f"Database error: {str(db_error)}")
            print(f"SQL Traceback: {traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=f"Database error: {str(db_error)}")
        finally:
            conn.close()

        # Get updated document details
        print(f"Fetching document details for doc_id: {doc_id}")
        docs_manager = GoogleDocsManager()
        doc_details = docs_manager.get_doc_details(doc_id)
        
        if not doc_details:
            print(f"No document details found for doc_id: {doc_id}")
            raise HTTPException(status_code=404, detail=f"Document details not found")
            
        print(f"Retrieved document details: {doc_details}")
        
        # Ensure status is updated in response
        doc_details['status'] = DocumentStatus.CASE_REVIEW_COMPLETE.value

        # Download the file
        print(f"Downloading document for doc_id: {doc_id}")
        file_path = docs_manager.download_doc(doc_id)
        print(f"File downloaded to: {file_path}")
        
        # Return both the file and document details
        return {
            "document": GoogleDocFile(**doc_details),
            "message": "Document approved and downloaded successfully"
        }
        
    except Exception as e:
        print(f"Error in approve_and_download_doc: {str(e)}")
        print(f"Full traceback: {traceback.format_exc()}")
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=str(e)) 
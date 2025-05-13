from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from typing import Optional, List
from pydantic import BaseModel
import sqlite3
import os
from datetime import datetime
import shutil
from pathlib import Path
from utils.google_docs import GoogleDocsManager
import re
from auth.auth_api import get_supabase_client  # Import the function we created earlier
from utils.supabase_document_ops import SupabaseDocumentOps

router = APIRouter(
    prefix="/documents",
    tags=["documents"]
)

class DocumentResponse(BaseModel):
    id: int
    title: str
    type: str
    url: str
    description: Optional[str]
    created_at: str
    department_name: str
    google_doc_id: Optional[str] = None
    google_doc_link: Optional[str] = None

class CaseFileRequest(BaseModel):
    file: UploadFile
    title: str
    description: Optional[str] = None

class UploadDocumentRequest(BaseModel):
    case_files: list[CaseFileRequest]
    department_name: str

def get_db_connection():
    conn = sqlite3.connect('medical_assessment.db')
    conn.row_factory = sqlite3.Row
    return conn

def validate_file_type(file: UploadFile) -> str:
    """Validate and return the file type"""
    # Get file extension
    file_extension = Path(file.filename).suffix.lower()
    
    # First check for markdown files by extension
    if file_extension in ['.md', '.markdown']:
        return 'MARKDOWN'
    
    # Then check for PDF by MIME type
    if file.content_type == 'application/pdf' and file_extension == '.pdf':
        return 'PDF'
    
    raise HTTPException(
        status_code=400,
        detail="Invalid file type. Only PDF (.pdf) and Markdown (.md, .markdown) files are allowed."
    )

@router.post("/upload", response_model=List[DocumentResponse])
async def upload_document(
    files: List[UploadFile] = File(...),
    titles: List[str] = Form(...),
    descriptions: List[str] = Form(None),
    department_name: str = Form(...),
    department_id: int = Form(...)
):
    """Upload multiple documents and optionally convert to Google Docs"""
    # Initialize uploaded_files list here so it's always defined
    uploaded_files = []
    
    try:
        # Get department ID from name
        # department_id = await SupabaseDocumentOps.get_department_id(department_name)
        
        # Create uploads directory if it doesn't exist
        upload_dir = Path(os.getenv("UPLOADS_DIR", "case-data/uploads"))
        upload_dir.mkdir(exist_ok=True)
        
        responses = []
        
        # Process each file
        for file, title, description in zip(files, titles, descriptions or [None] * len(files)):
            file_path = None
            try:
                # Check for duplicates
                is_duplicate = await SupabaseDocumentOps.check_duplicate(title, department_id)
                if is_duplicate:
                    raise HTTPException(
                        status_code=400,
                        detail=f"A document with title '{title}' already exists in this department"
                    )
                
                # Save the file
                file_path = upload_dir / file.filename
                with file_path.open("wb") as buffer:
                    shutil.copyfileobj(file.file, buffer)
                
                if file_path:
                    uploaded_files.append(file_path)
                                
                # Determine file type and handle accordingly
                file_type = "MARKDOWN" if file.filename.endswith('.md') else "PDF"
                google_doc_id = None
                google_doc_link = None
                
                if file_type == "MARKDOWN":
                    # Convert to Google Doc
                    docs_manager = GoogleDocsManager()
                    with open(file_path, 'r') as f:
                        content = f.read()
                    google_doc_id, google_doc_link = docs_manager.create_doc(title, content)
                
                # Insert document into Supabase
                doc_data = await SupabaseDocumentOps.insert_document(
                    title=title,
                    file_type=file_type,
                    url=str(file_path),
                    description=description,
                    google_doc_id=google_doc_id,
                    google_doc_link=google_doc_link,
                    department_id=department_id
                )
                
                # Format response
                response = {
                    "id": doc_data["id"],
                    "title": doc_data["title"],
                    "type": doc_data["type"],
                    "url": doc_data["url"],
                    "description": doc_data["description"],
                    "created_at": doc_data["created_at"],
                    "department_name": department_name,
                    "google_doc_id": doc_data.get("google_doc_id"),
                    "google_doc_link": doc_data.get("google_doc_link")
                }
                
                responses.append(DocumentResponse(**response))
                
            except Exception as e:
                # Clean up this file if there was an error
                if file_path and file_path.exists():
                    try:
                        os.remove(file_path)
                    except:
                        pass
                raise
        
        return responses
        
    except Exception as e:
        # Clean up any uploaded files
        for file_path in uploaded_files:
            try:
                if file_path.exists():
                    os.remove(file_path)
            except:
                pass
        
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/topic/{topic_name}", response_model=List[DocumentResponse])
async def get_topic_documents(topic_name: str):
    """
    Get all documents associated with a specific topic.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                d.id,
                d.title,
                d.type,
                d.url,
                d.description,
                d.created_at,
                d.google_doc_id,
                d.google_doc_link,
                t.name as topic_name
            FROM documents d
            JOIN topic_documents td ON d.id = td.document_id
            JOIN topics t ON td.topic_id = t.id
            WHERE LOWER(t.name) = LOWER(?)
            ORDER BY d.created_at DESC
        ''', (topic_name,))
        
        documents = cursor.fetchall()
        conn.close()
        
        return [
            DocumentResponse(
                id=doc['id'],
                title=doc['title'],
                type=doc['type'],
                url=doc['url'],
                description=doc['description'],
                created_at=doc['created_at'],
                topic_name=doc['topic_name'],
                google_doc_id=doc['google_doc_id'],
                google_doc_link=doc['google_doc_link']
            )
            for doc in documents
        ]

    except Exception as e:
        if conn:
            conn.close()
        raise HTTPException(status_code=500, detail=str(e)) 
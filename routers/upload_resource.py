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



class CaseFileRequest(BaseModel):
    file: UploadFile
    title: str
    description: Optional[str] = None

class UploadDocumentRequest(BaseModel):
    case_files: list[CaseFileRequest]
    department_name: str


@router.post("/upload", response_model=List[DocumentResponse])
async def upload_document(
    files: List[UploadFile] = File(...),
    titles: List[str] = Form(...),
    descriptions: List[str] = Form(None),
    department_name: str = Form(...)
):
    """
    Upload multiple documents and associate them with a department.
    """
    conn = None
    results = []
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get department ID (case-insensitive)
        cursor.execute('SELECT id FROM departments WHERE LOWER(name) = LOWER(?)', (department_name,))
        department = cursor.fetchone()
        if not department:
            raise HTTPException(status_code=404, detail=f"Department '{department_name}' not found")
        
        for file, title, description in zip(files, titles, descriptions):
            try:
                content = await file.read()
                content_str = content.decode('utf-8')
                if not content_str.strip():
                    raise ValueError("File content is empty")
                
                # Validate file type
                file_type = validate_file_type(file)
                safe_title = re.sub(r'[^a-zA-Z0-9-_]', '_', title).replace('_md', '.md')
                
                # Check for duplicates immediately
                cursor.execute('''
                    SELECT COUNT(*) as count 
                    FROM documents 
                    WHERE title = ? AND department_id = ?
                ''', (safe_title, department['id']))
                if cursor.fetchone()['count'] > 0:
                    raise HTTPException(
                        status_code=400,
                        detail=f"A document with title '{title}' already exists in this department"
                    )
                
                google_doc_id = None
                google_doc_link = None
                if file_type == 'MARKDOWN':
                    try:
                        if not content_str.strip():
                            raise ValueError("Markdown file is empty")
                        
                        # Create Google Doc
                        docs_manager = GoogleDocsManager()
                        google_doc_id, google_doc_link = docs_manager.create_doc(safe_title, content_str)
                        print(f"Created Google Doc with ID: {google_doc_id} and link: {google_doc_link}")
                    except UnicodeDecodeError as e:
                        raise HTTPException(
                            status_code=400,
                            detail="Invalid markdown file encoding. Please use UTF-8."
                        )
                
                # Insert into documents table
                cursor.execute('''
                    INSERT INTO documents (title, type, url, description, google_doc_id, google_doc_link, department_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    safe_title,
                    file_type,
                    google_doc_link if google_doc_link else f"/files/{file.filename}",
                    description,
                    google_doc_id,
                    google_doc_link,
                    department['id']
                ))
                
                document_id = cursor.lastrowid
                
                # Get the complete document data
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
                        dep.name as department_name
                    FROM documents d
                    JOIN departments dep ON d.department_id = dep.id
                    WHERE d.id = ?
                ''', (document_id,))
                
                document = cursor.fetchone()
                
                results.append(DocumentResponse(
                    id=document['id'],
                    title=document['title'],
                    type=document['type'],
                    url=document['url'],
                    description=document['description'],
                    created_at=document['created_at'],
                    department_name=document['department_name'],
                    google_doc_id=document['google_doc_id'],
                    google_doc_link=document['google_doc_link']
                ))
            except Exception as e:
                if conn:
                    conn.rollback()
                if isinstance(e, HTTPException):
                    raise
                raise HTTPException(status_code=500, detail=str(e))
        
        conn.commit()
        
        return results

    except Exception as e:
        if conn:
            conn.rollback()
            conn.close()
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()

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
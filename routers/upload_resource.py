from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from typing import Optional, List
from pydantic import BaseModel
import sqlite3
import os
from datetime import datetime
import shutil
from pathlib import Path

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
    topic_name: str

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

@router.post("/upload", response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    topic_name: str = Form(...),
    title: str = Form(...),
    description: Optional[str] = Form(None)
):
    """
    Upload a document file (PDF or Markdown) and associate it with a topic.
    """
    conn = None
    try:
        # Validate file type
        file_type = validate_file_type(file)
        
        # Validate file extension
        allowed_extensions = {'.pdf', '.md', '.markdown'}
        file_extension = Path(file.filename).suffix.lower()
        if file_extension not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file extension. Allowed extensions are: {', '.join(allowed_extensions)}"
            )
        
        # Create upload directory if it doesn't exist
        upload_dir = Path("uploads")
        upload_dir.mkdir(exist_ok=True)
        
        # Generate unique filename while preserving extension
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_filename = f"{timestamp}{file_extension}"
        file_path = upload_dir / safe_filename
        
        # Save the file
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # For markdown files, validate the content structure (optional)
        if file_type == 'MARKDOWN':
            try:
                with open(file_path, 'r', encoding='utf-8') as md_file:
                    content = md_file.read()
                    # You could add additional markdown validation here if needed
                    if not content.strip():
                        raise ValueError("Markdown file is empty")
            except UnicodeDecodeError:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid markdown file encoding. Please use UTF-8."
                )
        
        # Connect to database
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get topic ID
        cursor.execute('SELECT id FROM topics WHERE name = ?', (topic_name,))
        topic = cursor.fetchone()
        
        if not topic:
            raise HTTPException(status_code=404, detail=f"Topic '{topic_name}' not found")
        
        # Insert into documents table with proper URL format
        cursor.execute('''
            INSERT INTO documents (title, type, url, description)
            VALUES (?, ?, ?, ?)
        ''', (
            title,
            file_type,
            f"/files/{safe_filename}",  # Use relative URL path
            description
        ))
        
        document_id = cursor.lastrowid
        
        # Create topic-document association
        cursor.execute('''
            INSERT INTO topic_documents (topic_id, document_id)
            VALUES (?, ?)
        ''', (topic['id'], document_id))
        
        # Get the complete document data
        cursor.execute('''
            SELECT 
                d.id,
                d.title,
                d.type,
                d.url,
                d.description,
                d.created_at,
                t.name as topic_name
            FROM documents d
            JOIN topic_documents td ON d.id = td.document_id
            JOIN topics t ON td.topic_id = t.id
            WHERE d.id = ?
        ''', (document_id,))
        
        document = cursor.fetchone()
        conn.commit()
        conn.close()
        
        return DocumentResponse(
            id=document['id'],
            title=document['title'],
            type=document['type'],
            url=document['url'],
            description=document['description'],
            created_at=document['created_at'],
            topic_name=document['topic_name']
        )

    except Exception as e:
        if conn:
            conn.close()
        # Clean up file if database operation failed
        if 'file_path' in locals() and file_path.exists():
            file_path.unlink()
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
                t.name as topic_name
            FROM documents d
            JOIN topic_documents td ON d.id = td.document_id
            JOIN topics t ON td.topic_id = t.id
            WHERE t.name = ?
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
                topic_name=doc['topic_name']
            )
            for doc in documents
        ]

    except Exception as e:
        if conn:
            conn.close()
        raise HTTPException(status_code=500, detail=str(e)) 
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from typing import Optional, List
from pydantic import BaseModel
import sqlite3
import os
from datetime import datetime
import shutil
from pathlib import Path
from utils.google_docs import GoogleDocsManager

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
    google_doc_id: Optional[str] = None
    google_doc_link: Optional[str] = None

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
    google_doc_id = None
    google_doc_link = None
    try:
        print(f"Starting upload process for file: {file.filename}, topic: {topic_name}, title: {title}")
        
        # Validate file type
        try:
            file_type = validate_file_type(file)
            print(f"File type validated: {file_type}")
        except Exception as e:
            print(f"File type validation error: {str(e)}")
            raise
        
        # Validate file extension
        try:
            allowed_extensions = {'.pdf', '.md', '.markdown'}
            file_extension = Path(file.filename).suffix.lower()
            if file_extension not in allowed_extensions:
                error_msg = f"Invalid file extension. Allowed extensions are: {', '.join(allowed_extensions)}"
                print(error_msg)
                raise HTTPException(status_code=400, detail=error_msg)
            print(f"File extension validated: {file_extension}")
        except Exception as e:
            if not isinstance(e, HTTPException):
                print(f"File extension validation error: {str(e)}")
                raise HTTPException(status_code=400, detail=str(e))
            else:
                raise
        
        # Create upload directory if it doesn't exist
        try:
            upload_dir = Path("uploads")
            upload_dir.mkdir(exist_ok=True)
            print(f"Upload directory ensured: {upload_dir}")
        except Exception as e:
            print(f"Error creating upload directory: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error creating upload directory: {str(e)}")
        
        # Generate unique filename while preserving extension
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_filename = f"{timestamp}{file_extension}"
            file_path = upload_dir / safe_filename
            print(f"Generated safe filename: {safe_filename}")
        except Exception as e:
            print(f"Error generating filename: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error generating filename: {str(e)}")
        
        # Save the file
        try:
            with file_path.open("wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            print(f"File saved to: {file_path}")
        except Exception as e:
            print(f"Error saving file: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error saving file: {str(e)}")
        
        # For markdown files, validate and create Google Doc
        if file_type == 'MARKDOWN':
            try:
                print("Processing markdown file...")
                with open(file_path, 'r', encoding='utf-8') as md_file:
                    content = md_file.read()
                    if not content.strip():
                        print("Markdown file is empty")
                        raise ValueError("Markdown file is empty")
                    print(f"Read markdown content, length: {len(content)} characters")
                    
                    # Create Google Doc
                    print("Initializing GoogleDocsManager...")
                    docs_manager = GoogleDocsManager()
                    print("Calling create_doc method...")
                    google_doc_id, google_doc_link = docs_manager.create_doc(title, content)
                    print(f"Created Google Doc with ID: {google_doc_id} and link: {google_doc_link}")
            except UnicodeDecodeError as e:
                print(f"Unicode decode error: {str(e)}")
                raise HTTPException(
                    status_code=400,
                    detail="Invalid markdown file encoding. Please use UTF-8."
                )
            except Exception as e:
                print(f"Error processing markdown file: {str(e)}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Error processing markdown file: {str(e)}"
                )
        
        # Connect to database
        try:
            print("Connecting to database...")
            conn = get_db_connection()
            cursor = conn.cursor()
            print("Database connection established")
        except Exception as e:
            print(f"Database connection error: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Database connection error: {str(e)}")
        
        # Get topic ID
        try:
            print(f"Looking up topic: {topic_name}")
            cursor.execute('SELECT id FROM topics WHERE name = ?', (topic_name,))
            topic = cursor.fetchone()
            
            if not topic:
                print(f"Topic not found: {topic_name}")
                raise HTTPException(status_code=404, detail=f"Topic '{topic_name}' not found")
            print(f"Found topic with ID: {topic['id']}")
        except Exception as e:
            if not isinstance(e, HTTPException):
                print(f"Topic lookup error: {str(e)}")
                raise HTTPException(status_code=500, detail=f"Topic lookup error: {str(e)}")
            else:
                raise
        
        # Insert into documents table with proper URL format
        try:
            print("Inserting document into database...")
            cursor.execute('''
                INSERT INTO documents (title, type, url, description, google_doc_id, google_doc_link)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                title,
                file_type,
                f"/files/{safe_filename}",
                description,
                google_doc_id,
                google_doc_link
            ))
            
            document_id = cursor.lastrowid
            print(f"Document inserted with ID: {document_id}")
        except Exception as e:
            print(f"Document insertion error: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Document insertion error: {str(e)}")
        
        # Create topic-document association
        try:
            print(f"Creating topic-document association: topic_id={topic['id']}, document_id={document_id}")
            cursor.execute('''
                INSERT INTO topic_documents (topic_id, document_id)
                VALUES (?, ?)
            ''', (topic['id'], document_id))
            print("Topic-document association created")
        except Exception as e:
            print(f"Topic-document association error: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Topic-document association error: {str(e)}")
        
        # Get the complete document data
        try:
            print(f"Retrieving complete document data for ID: {document_id}")
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
                WHERE d.id = ?
            ''', (document_id,))
            
            document = cursor.fetchone()
            print("Document data retrieved")
        except Exception as e:
            print(f"Document retrieval error: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Document retrieval error: {str(e)}")
        
        try:
            print("Committing database transaction...")
            conn.commit()
            print("Database transaction committed")
        except Exception as e:
            print(f"Database commit error: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Database commit error: {str(e)}")
        
        try:
            print("Closing database connection...")
            conn.close()
            print("Database connection closed")
        except Exception as e:
            print(f"Database close error: {str(e)}")
            # Don't raise an exception here, as we've already committed
        
        print("Preparing response...")
        response = DocumentResponse(
            id=document['id'],
            title=document['title'],
            type=document['type'],
            url=document['url'],
            description=document['description'],
            created_at=document['created_at'],
            topic_name=document['topic_name'],
            google_doc_id=document['google_doc_id'],
            google_doc_link=document['google_doc_link']
        )
        print("Response prepared, returning to client")
        return response

    except Exception as e:
        print(f"CRITICAL ERROR in upload_document: {str(e)}")
        if conn:
            try:
                conn.close()
                print("Database connection closed after error")
            except Exception as close_error:
                print(f"Error closing database connection: {str(close_error)}")
        
        # Clean up file if database operation failed
        if 'file_path' in locals() and file_path.exists():
            try:
                file_path.unlink()
                print(f"Cleaned up file: {file_path}")
            except Exception as cleanup_error:
                print(f"Error cleaning up file: {str(cleanup_error)}")
        
        if isinstance(e, HTTPException):
            print(f"Raising HTTPException: {e.detail}")
            raise
        else:
            print(f"Converting exception to HTTPException: {str(e)}")
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
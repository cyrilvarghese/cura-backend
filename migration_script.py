import sqlite3
from supabase import create_client, Client
import os
from datetime import datetime
from typing import List, Dict, Any
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Environment validation
required_env_vars = ["SUPABASE_URL", "SUPABASE_KEY"]
missing_vars = [var for var in required_env_vars if not os.getenv(var)]
if missing_vars:
    raise EnvironmentError(f"Missing required environment variables: {', '.join(missing_vars)}")

def get_supabase_client() -> Client:
    """Initialize and validate Supabase client connection."""
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    
    if not url:
        raise EnvironmentError("SUPABASE_URL not configured")
    if not key:
        raise EnvironmentError("SUPABASE_KEY not configured")
        
    return create_client(url, key)

# Initialize Supabase client
try:
    supabase = get_supabase_client()
    logging.info("✓ Supabase client initialized successfully")
except Exception as e:
    logging.error(f"❌ Failed to initialize Supabase client: {e}")
    raise

def validate_document(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and clean document data before insertion."""
    # Convert datetime to ISO format string
    if isinstance(doc.get('created_at'), datetime):
        doc['created_at'] = doc['created_at'].isoformat()
    elif isinstance(doc.get('created_at'), str):
        try:
            # Convert string to datetime then back to ISO format string
            doc['created_at'] = datetime.fromisoformat(
                doc['created_at'].replace(' ', 'T')
            ).isoformat()
        except ValueError:
            logging.warning(f"Invalid date format for document {doc.get('id')}")
    
    # Validate status
    valid_statuses = {
        'CASE_REVIEW_PENDING', 'CASE_REVIEW_IN_PROGRESS', 
        'CASE_REVIEW_COMPLETE', 'DATA_REVIEW_IN_PROGRESS', 'PUBLISHED'
    }
    if doc.get('status') and doc['status'] not in valid_statuses:
        logging.warning(f"Invalid status for document {doc.get('id')}: {doc.get('status')}")
        doc['status'] = 'CASE_REVIEW_PENDING'  # Default value
    
    return doc

def migrate_departments(batch_size: int = 100) -> Dict[int, int]:
    """
    Migrate departments and return mapping of old IDs to new IDs.
    Returns: Dict[old_id, new_id]
    """
    try:
        conn = sqlite3.connect("medical_assessment.db")
        cursor = conn.cursor()
        
        # Get departments count
        cursor.execute("SELECT COUNT(*) FROM departments")
        total_departments = cursor.fetchone()[0]
        logging.info(f"Found {total_departments} departments to migrate")
        
        # Fetch all departments
        cursor.execute("SELECT id, name FROM departments")
        columns = [description[0] for description in cursor.description]
        
        id_mapping = {}
        processed = 0
        
        while True:
            rows = cursor.fetchmany(batch_size)
            if not rows:
                break
                
            departments = [dict(zip(columns, row)) for row in rows]
            
            try:
                # Insert and get the response to map IDs
                res = supabase.table("departments").insert(
                    [{"name": dept["name"]} for dept in departments]
                ).execute()
                
                # Map old IDs to new IDs
                for old_dept, new_dept in zip(departments, res.data):
                    id_mapping[old_dept["id"]] = new_dept["id"]
                
                processed += len(departments)
                logging.info(f"Migrated departments: {processed}/{total_departments}")
                
            except Exception as e:
                logging.error(f"Error inserting department batch: {e}")
                
        logging.info("✓ Departments migration complete")
        return id_mapping
        
    except Exception as e:
        logging.error(f"Department migration failed: {e}")
        raise
    finally:
        conn.close()

def migrate_documents(department_mapping: Dict[int, int], batch_size: int = 100) -> None:
    """Migrate documents using the department ID mapping."""
    try:
        conn = sqlite3.connect("medical_assessment.db")
        cursor = conn.cursor()
        
        # Get total count
        cursor.execute("SELECT COUNT(*) FROM documents")
        total_documents = cursor.fetchone()[0]
        
        # Fetch all documents
        cursor.execute("""
            SELECT id, title, type, url, description, 
                   google_doc_id, google_doc_link, department_id, 
                   status, created_at 
            FROM documents
        """)
        columns = [description[0] for description in cursor.description]
        
        processed = 0
        while True:
            rows = cursor.fetchmany(batch_size)
            if not rows:
                break
                
            # Convert rows to dictionaries and validate
            documents = []
            for row in rows:
                doc = dict(zip(columns, row))
                # Map old department_id to new department_id
                if doc.get('department_id'):
                    doc['department_id'] = department_mapping.get(
                        doc['department_id'],
                        None  # Set to None if mapping not found
                    )
                documents.append(validate_document(doc))
            
            try:
                res = supabase.table("documents").insert(documents).execute()
                processed += len(documents)
                logging.info(f"Documents progress: {processed}/{total_documents}")
            except Exception as e:
                logging.error(f"Error inserting document batch: {e}")
                
    except Exception as e:
        logging.error(f"Documents migration failed: {e}")
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    try:
        # First migrate departments and get ID mapping
        logging.info("Starting departments migration...")
        department_mapping = migrate_departments()
        
        # Then migrate documents using department mapping
        logging.info("Starting documents migration...")
        migrate_documents(department_mapping)
        
        logging.info("✅ Migration completed successfully")
    except Exception as e:
        logging.error(f"❌ Migration failed: {e}") 
from typing import Dict, Any, List, Optional
from auth.auth_api import get_supabase_client, get_user, get_user_from_token
from fastapi import HTTPException
import os
from dotenv import load_dotenv
import re

from utils.file_ops import export_file
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Load environment variables
load_dotenv()

class SupabaseDocumentOps:
    """Handles all Supabase document operations"""
    
    @staticmethod
    def get_client(use_service_role: bool = False):
        """Get Supabase client with appropriate permissions"""
        return get_supabase_client(use_service_role=use_service_role)

    @staticmethod
    async def insert_document(
        title: str,
        file_type: str,
        url: str,
        description: Optional[str],
        google_doc_id: Optional[str],
        google_doc_link: Optional[str],
        department_id: int
    ) -> Dict[str, Any]:
        """Insert a new document into Supabase"""
        try:
            # Create safe filename from title
            safe_filename = title.replace('.md', '')  # Remove .md extension if it exists
            safe_filename = re.sub(r'[^a-zA-Z0-9-_]', '_', safe_filename)
            
            # Add appropriate extension based on file type
            if file_type == 'MARKDOWN':
                file_name = f"{safe_filename}.md"
            else:
                file_name = f"{safe_filename}.pdf"
            
            supabase = SupabaseDocumentOps.get_client()
            
            result = supabase.table("documents").insert({
                "title": safe_filename,  # Use safe filename as title
                "type": file_type,
                "url": url,
                "description": description,
                "google_doc_id": google_doc_id,
                "google_doc_link": google_doc_link,
                "department_id": department_id,
                "status": "CASE_REVIEW_PENDING",
         
            }).execute()
            
            return result.data[0] if result.data else None
            
        except Exception as e:
            print(f"Supabase document insertion error: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to insert document: {str(e)}"
            )

    @staticmethod
    async def check_duplicate(
        title: str,
        department_id: int
    ) -> bool:
        """Check if a document with the same title exists in the department"""
        try:
            supabase = SupabaseDocumentOps.get_client()
            
            result = supabase.table("documents")\
                .select("id")\
                .eq("title", title)\
                .eq("department_id", department_id)\
                .execute()
                
            return bool(result.data)
            
        except Exception as e:
            print(f"Supabase duplicate check error: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to check for duplicates: {str(e)}"
            )

    @staticmethod
    async def get_department_id(department_name: str) -> int:
        """Get department ID by name"""
        try:
            supabase = SupabaseDocumentOps.get_client()
            
            result = supabase.table("departments")\
                .select("id")\
                .ilike("name", department_name)\
                .execute()
                
            if not result.data:
                raise HTTPException(
                    status_code=404,
                    detail=f"Department '{department_name}' not found"
                )
                
            return result.data[0]['id']
            
        except HTTPException:
            raise
        except Exception as e:
            print(f"Supabase department lookup error: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to lookup department: {str(e)}"
            )

    @staticmethod
    async def update_document_status(
        google_doc_id: str,
        status: str
    ) -> Dict[str, Any]:
        """Update document status"""
        try:
            supabase = SupabaseDocumentOps.get_client()
            
            result = supabase.table("documents")\
                .update({"status": status})\
                .eq("google_doc_id", google_doc_id)\
                .execute()
                
            if not result.data:
                raise HTTPException(
                    status_code=404,
                    detail=f"Document with google_doc_id '{google_doc_id}' not found"
                )
                
            return result.data[0]
            
        except HTTPException:
            raise
        except Exception as e:
            print(f"Supabase status update error: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to update document status: {str(e)}"
            )

    @staticmethod
    async def get_documents_by_topic(topic_name: str) -> List[Dict[str, Any]]:
        """Get all documents for a specific topic"""
        try:
            supabase = SupabaseDocumentOps.get_client()
            
            result = supabase.table("documents")\
                .select(
                    "id, title, type, url, description, created_at, "
                    "google_doc_id, google_doc_link, status, "
                    "topics!inner(name)"
                )\
                .eq("topics.name", topic_name)\
                .execute()
                
            return result.data
            
        except Exception as e:
            print(f"Supabase topic documents lookup error: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to fetch topic documents: {str(e)}"
            )

    @staticmethod
    def _get_drive_service():
        """Get Google Drive service instance"""
        credentials = service_account.Credentials.from_service_account_file(
            '/etc/secrets/service-account-key', 
            scopes=['https://www.googleapis.com/auth/drive.file']
        )
        return build('drive', 'v3', credentials=credentials)

    @staticmethod
    async def approve_document(google_doc_id: str, token: str) -> Dict[str, Any]:
        """
        Approve a document by:
        1. Setting status to CASE_REVIEW_COMPLETE
        2. Adding approval metadata (approver info and timestamp)
        3. Exporting the file to uploads directory
        4. Returning updated document details
        """
        try:
            supabase = SupabaseDocumentOps.get_client()
            
            # Get current user info for approval metadata
            user_info = await SupabaseDocumentOps.check_user_permission(token)
            print("Updating doc with ID:", repr(google_doc_id))
            
            # Update the document with approval info
            result = supabase.table("documents")\
                .update({
                    "status": "CASE_REVIEW_COMPLETE",
                    "approved_by": user_info["id"],
                    "approved_by_email": user_info["email"],
                    "approved_by_username": user_info.get("username"),
                    "approved_at": "now()"  # Supabase will set server timestamp
                })\
                .eq("google_doc_id", google_doc_id)\
                .execute()
                
            if not result.data:
                raise HTTPException(
                    status_code=404,
                    detail=f"Document with google_doc_id '{google_doc_id}' not found"
                )
            
            # Get the complete document details including department
            doc_details = supabase.table("documents")\
                .select(
                    "*, departments(name)"
                )\
                .eq("google_doc_id", google_doc_id)\
                .single()\
                .execute()

            if doc_details.data:
                try:
                    # Create uploads directory if it doesn't exist
                    upload_dir = os.getenv("UPLOADS_DIR", "case-data/uploads")
                    os.makedirs(upload_dir, exist_ok=True)
                    
                    # Get drive service
                    drive_service = SupabaseDocumentOps._get_drive_service()
                    
                    # Export the file
                    doc_type = doc_details.data.get('type', 'PDF')
                    file_path, response = export_file(drive_service, google_doc_id, doc_type)
                    full_path = os.path.join(upload_dir, os.path.basename(file_path))
                    
                    # Write the file
                    with open(full_path, 'wb') as f:
                        f.write(response)
                    
                    print(f"Document exported successfully to: {full_path}")
                    
                    # Update document with file path
                    supabase.table("documents")\
                        .update({"exported_file_path": full_path})\
                        .eq("google_doc_id", google_doc_id)\
                        .execute()
                        
                except Exception as export_error:
                    print(f"Warning: Failed to export document: {str(export_error)}")
                    
            return doc_details.data
                
        except HTTPException:
            raise
        except Exception as e:
            print(f"Supabase document approval error: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to approve document: {str(e)}"
            )

    @staticmethod
    async def check_user_permission(token: str) -> Dict[str, Any]:
        """Check if user has admin or teacher role"""
        user_response = await get_user_from_token(token)
        if not user_response.get("success"):
            raise HTTPException(
                status_code=401,
                detail="Unable to get user information"
            )
        
        user_role = user_response["user"].get("role")
        if user_role not in ["admin", "teacher"]:
            raise HTTPException(
                status_code=403,
                detail="Only admin and teacher roles can perform this action"
            )
            
        return user_response["user"]

    @staticmethod
    async def get_department_documents(department_name: str) -> List[Dict[str, Any]]:
        """Get all documents for a specific department"""
        try:
            supabase = SupabaseDocumentOps.get_client()
            
            result = supabase.table("documents")\
                .select("*")\
                .eq("department_id", department_name)\
                .order("created_at", desc=True)\
                .execute()
            
            print(f"Department documents query result: {result.data}")
            return result.data if result.data else []
            
        except Exception as e:
            print(f"Supabase department documents lookup error: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to fetch department documents: {str(e)}"
            )

    @staticmethod
    async def delete_document(google_doc_id: str) -> Dict[str, Any]:
        """Delete a document from Supabase by google_doc_id"""
        try:
            supabase = SupabaseDocumentOps.get_client()
            
            # Delete the document
            result = supabase.table("documents")\
                .delete()\
                .eq("google_doc_id", google_doc_id)\
                .execute()
                
            if not result.data:
                raise HTTPException(
                    status_code=404,
                    detail=f"Document with google_doc_id '{google_doc_id}' not found"
                )
                
            return {"success": True, "message": f"Document with ID {google_doc_id} deleted successfully"}
            
        except HTTPException:
            raise
        except Exception as e:
            print(f"Supabase document deletion error: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to delete document: {str(e)}"
            ) 
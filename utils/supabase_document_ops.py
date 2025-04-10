from typing import Dict, Any, List, Optional
from auth.auth_api import get_supabase_client
from fastapi import HTTPException

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
            supabase = SupabaseDocumentOps.get_client(use_service_role=True)
            
            result = supabase.table("documents").insert({
                "title": title,
                "type": file_type,
                "url": url,
                "description": description,
                "google_doc_id": google_doc_id,
                "google_doc_link": google_doc_link,
                "department_id": department_id,
                "status": "CASE_REVIEW_PENDING"
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
            supabase = SupabaseDocumentOps.get_client(use_service_role=True)
            
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
    async def approve_document(google_doc_id: str) -> Dict[str, Any]:
        """
        Approve a document by:
        1. Setting status to CASE_REVIEW_COMPLETE
        2. Returning updated document details
        """
        try:
            supabase = SupabaseDocumentOps.get_client(use_service_role=True)
            
            # Update the document status
            result = supabase.table("documents")\
                .update({"status": "CASE_REVIEW_COMPLETE"})\
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
                
            return doc_details.data
            
        except HTTPException:
            raise
        except Exception as e:
            print(f"Supabase document approval error: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to approve document: {str(e)}"
            ) 
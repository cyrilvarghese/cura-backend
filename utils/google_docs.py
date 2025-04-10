import os
from google.oauth2 import service_account
from googleapiclient.discovery import build
from fastapi import HTTPException
from typing import Optional, List, Dict, Any, Tuple
import re
import traceback
from utils.file_ops import export_file
from auth.auth_api import get_client
from datetime import datetime
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload
from googleapiclient.errors import HttpError
import socket

from utils.supabase_document_ops import SupabaseDocumentOps

SCOPES = ['https://www.googleapis.com/auth/drive.file']
# SERVICE_ACCOUNT_FILE = 'utils/service-account-key.json'
print("File exists:", os.path.exists('/etc/secrets/service-account-key'))
SERVICE_ACCOUNT_FILE = '/etc/secrets/service-account-key'
FOLDER_NAME = 'cases-for-review'

class GoogleDocsManager:
    def __init__(self):
        try:
            # Set timeout first
            self.timeout = 20  # Set default timeout
            
            print(f"Initializing Google Docs Manager with service account file: {SERVICE_ACCOUNT_FILE}")
            self.credentials = service_account.Credentials.from_service_account_file(
                SERVICE_ACCOUNT_FILE, scopes=SCOPES 
            )
            print("Successfully loaded credentials")
            
            print("Building Google Docs service...")
            self.docs_service = build('docs', 'v1', credentials=self.credentials)
            print("Building Google Drive service...")
            self.drive_service = build('drive', 'v3', credentials=self.credentials)
            print("Successfully initialized Google services")
            
            # Get or create the folder
            self.folder_id = self._get_or_create_folder()
            print(f"Using folder ID: {self.folder_id}")
            
        except Exception as e:
            print(f"Error initializing Google services: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to initialize Google services: {str(e)}"
            )

    def _execute_with_timeout(self, request):
        """Execute a Google API request with timeout"""
        try:
            socket.setdefaulttimeout(self.timeout)
            return request.execute()
        except socket.timeout:
            print("API request timed out")
            raise HTTPException(
                status_code=504,
                detail="Google API request timed out"
            )
        except HttpError as e:
            print(f"Google API error: {str(e)}")
            raise HTTPException(
                status_code=e.resp.status,
                detail=f"Google API error: {str(e)}"
            )
        finally:
            socket.setdefaulttimeout(None)  # Reset timeout

    def _get_or_create_folder(self) -> str:
        """Get the folder ID if it exists, or create it if it doesn't"""
        try:
            print(f"Searching for folder: {FOLDER_NAME}")
            # Search for the folder
            request = self.drive_service.files().list(
                q=f"name='{FOLDER_NAME}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
                spaces='drive',
                fields='files(id, name)'
            )
            results = self._execute_with_timeout(request)
            
            files = results.get('files', [])
            
            # If folder exists, return its ID
            if files:
                print(f"Found existing folder with ID: {files[0]['id']}")
                return files[0]['id']
            
            # If folder doesn't exist, create it
            print(f"Creating new folder: {FOLDER_NAME}")
            folder_metadata = {
                'name': FOLDER_NAME,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            
            request = self.drive_service.files().create(
                body=folder_metadata,
                fields='id'
            )
            folder = self._execute_with_timeout(request)
            
            print(f"Created new folder with ID: {folder['id']}")
            return folder['id']
            
        except Exception as e:
            print(f"Error managing folder: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to manage folder: {str(e)}"
            )

    def create_doc(self, title: str, content: str) -> tuple[str, str]:
        """Create a Google Doc with formatted Markdown content and return its ID and web link"""
        try:
            # Create safe filename
            safe_title = re.sub(r'[^a-zA-Z0-9-_]', '_', title).replace('_md', '.md')
            
            print(f"Creating new Google Doc with title: {safe_title}")
            
            # Create an empty doc in the folder
            doc_body = {
                'name': safe_title,
                'mimeType': 'application/vnd.google-apps.document',
                'parents': [self.folder_id]
            }
            print("Creating empty document...")
            doc = self.drive_service.files().create(
                body=doc_body,
                fields='id'
            ).execute()
            
            doc_id = doc['id']
            doc_link = f"https://docs.google.com/document/d/{doc_id}/edit"
            print(f"Created document with ID: {doc_id} and link: {doc_link}")

            # Insert the content
            print("Inserting content into document...")
            requests = [
                {
                    'insertText': {
                        'location': {
                            'index': 1
                        },
                        'text': content
                    }
                }
            ]
            
            self.docs_service.documents().batchUpdate(
                documentId=doc_id,
                body={'requests': requests}
            ).execute()
            print("Successfully inserted content into document")

            # Set permissions to allow anyone with the link to edit and comment
            print("Setting document permissions...")
            permission = {
                'type': 'anyone',  # Anyone with the link
                'role': 'writer',  # Can edit, comment, and view
                'allowFileDiscovery': False  # Not discoverable in search
            }
            
            self.drive_service.permissions().create(
                fileId=doc_id,
                body=permission,
                fields='id',
                sendNotificationEmail=False  # Don't send notification emails
            ).execute()
            print("Document permissions set to allow anyone with the link to edit and comment")

            return doc_id, doc_link
        except Exception as e:
            print(f"Error creating document: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to create document: {str(e)}"
            )

    def _convert_markdown_to_requests(self, markdown_content: str) -> List[Dict[str, Any]]:
        """Convert markdown content to Google Docs API requests"""
        requests = []
        
        # First, insert the entire text
        requests.append({
            'insertText': {
                'location': {
                    'index': 1
                },
                'text': markdown_content
            }
        })
        
        # Track the current index in the document
        current_index = 1
        
        # Process headers (# Header)
        header_sizes = {
            1: 20,  # H1
            2: 16,  # H2
            3: 14,  # H3
            4: 12,  # H4
            5: 11,  # H5
            6: 10   # H6
        }
        
        for match in re.finditer(r'^(#{1,6})\s+(.+)$', markdown_content, re.MULTILINE):
            header_level = len(match.group(1))
            header_text = match.group(2)
            start_index = current_index + match.start()
            end_index = current_index + match.end()
            
            # Style the header
            requests.append({
                'updateTextStyle': {
                    'range': {
                        'startIndex': start_index,
                        'endIndex': end_index
                    },
                    'textStyle': {
                        'fontSize': {
                            'magnitude': header_sizes.get(header_level, 11),
                            'unit': 'PT'
                        },
                        'weightedFontFamily': {
                            'fontFamily': 'Arial',
                            'weight': 700
                        },
                        'bold': True
                    },
                    'fields': 'fontSize,weightedFontFamily,bold'
                }
            })
        
        # Process bold text (**bold** or __bold__)
        for match in re.finditer(r'(\*\*|__)(.*?)\1', markdown_content):
            bold_text = match.group(2)
            start_index = current_index + match.start()
            end_index = current_index + match.end()
            
            # Style the bold text
            requests.append({
                'updateTextStyle': {
                    'range': {
                        'startIndex': start_index,
                        'endIndex': end_index
                    },
                    'textStyle': {
                        'bold': True
                    },
                    'fields': 'bold'
                }
            })
        
        # Process italic text (*italic* or _italic_)
        for match in re.finditer(r'(\*|_)(.*?)\1', markdown_content):
            italic_text = match.group(2)
            start_index = current_index + match.start()
            end_index = current_index + match.end()
            
            # Style the italic text
            requests.append({
                'updateTextStyle': {
                    'range': {
                        'startIndex': start_index,
                        'endIndex': end_index
                    },
                    'textStyle': {
                        'italic': True
                    },
                    'fields': 'italic'
                }
            })
        
        # Process bullet lists
        for match in re.finditer(r'^(\s*[-*+]\s+.+)$', markdown_content, re.MULTILINE):
            list_item = match.group(1)
            start_index = current_index + match.start()
            end_index = current_index + match.end()
            
            # Create a bullet list
            requests.append({
                'createParagraphBullets': {
                    'range': {
                        'startIndex': start_index,
                        'endIndex': end_index
                    },
                    'bulletPreset': 'BULLET_DISC_CIRCLE_SQUARE'
                }
            })
        
        # Process numbered lists
        for match in re.finditer(r'^(\s*\d+\.\s+.+)$', markdown_content, re.MULTILINE):
            list_item = match.group(1)
            start_index = current_index + match.start()
            end_index = current_index + match.end()
            
            # Create a numbered list
            requests.append({
                'createParagraphBullets': {
                    'range': {
                        'startIndex': start_index,
                        'endIndex': end_index
                    },
                    'bulletPreset': 'NUMBERED_DECIMAL'
                }
            })
        
        return requests 

    def delete_doc(self, doc_id: str) -> bool:
        """Delete a Google Doc and its database record"""
        try:
            print(f"Deleting document with ID: {doc_id}")
            
            # First delete from Google Drive
            self.drive_service.files().delete(fileId=doc_id).execute()
            
            # Delete from Supabase
            supabase = SupabaseDocumentOps.get_client(use_service_role=True)
            result = supabase.table("documents")\
                .delete()\
                .eq("google_doc_id", doc_id)\
                .execute()
            
            print(f"Successfully deleted document {doc_id} from Drive and database")
            return True
            
        except Exception as e:
            print(f"Error deleting document: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to delete document: {str(e)}"
            )

    def get_doc_details(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get details for a single Google Doc file"""
        try:
            print(f"Getting details for document ID: {doc_id}")
            
            # Get file details from Google Drive
            file = self.drive_service.files().get(
                fileId=doc_id,
                fields="id, name, webViewLink, createdTime, modifiedTime"
            ).execute()

            # Get status from Supabase
            supabase = SupabaseDocumentOps.get_client()
            supabase_result = supabase.table("documents")\
                .select("status")\
                .eq("google_doc_id", doc_id)\
                .execute()
            
            # Use Supabase status or default
            status = (
                supabase_result.data[0]['status'] if supabase_result.data
                else 'CASE_REVIEW_PENDING'
            )

            doc_details = {
                "id": file['id'],
                "name": file['name'],
                "webViewLink": file['webViewLink'],
                "createdTime": file['createdTime'],
                "modifiedTime": file['modifiedTime'],
                "commentCount": 0,
                "status": status
            }
            print(f"Retrieved document details: {doc_details}")
            return doc_details

        except Exception as e:
            print(f"Error getting document details: {str(e)}")
            print(f"Full traceback: {traceback.format_exc()}")
            return None

    def list_folder_files(self) -> list:
        """List all files in the designated folder with their statuses"""
        try:
            # Get files from Google Drive
            results = self.drive_service.files().list(
                q=f"'{self.folder_id}' in parents",
                pageSize=100,
                fields="files(id, name, webViewLink, createdTime, modifiedTime)"
            ).execute()
            files = results.get('files', [])

            # Get Supabase client and log auth info
            supabase = get_client()
            session = supabase.auth.get_session()
            
            
            
            # Query will automatically include auth headers
            supabase_result = supabase.table("documents")\
                .select("google_doc_id, status, approved_by, approved_at, approved_by_email, approved_by_username")\
                .execute()
            
             # Create a dictionary of document data from Supabase
            supabase_docs = {
                doc['google_doc_id']: {
                    'status': doc['status'],
                    'approved_by': doc['approved_by'],
                    'approved_at': doc['approved_at'],
                    'approved_by_email': doc['approved_by_email'],
                    'approved_by_username': doc['approved_by_username']
                } 
                for doc in supabase_result.data
            } if supabase_result.data else {}

            # Combine Drive and Supabase data
            for file in files:
                doc_data = supabase_docs.get(file['id'], {
                    'status': 'CASE_REVIEW_PENDING',
                    'approved_by': None,
                    'approved_at': None,
                    'approved_by_email': None,
                    'approved_by_username': None
                })
                
                file['status'] = doc_data['status']
                file['approved_by'] = doc_data['approved_by']
                file['approved_at'] = doc_data['approved_at']
                file['approved_by_email'] = doc_data['approved_by_email']
                file['approved_by_username'] = doc_data['approved_by_username']

            return files

        except Exception as e:
            print(f"Error listing files: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to list files: {str(e)}"
            )

    def get_unresolved_comment_count(self, doc_id: str) -> int:
        """Get the count of unresolved comments for a specific document"""
        try:
            print(f"Getting unresolved comment count for document {doc_id}")
            
            # Make sure we have the right scope for accessing comments
            # For Drive files, we need to use the Drive API to get comments
            comments = self.drive_service.comments().list(
                fileId=doc_id,
                fields="comments(resolved)",
                includeDeleted=False
            ).execute()
            
            # Count unresolved comments
            unresolved_count = 0
            for comment in comments.get('comments', []):
                if comment.get('resolved') is False:
                    unresolved_count += 1
            
            print(f"Found {unresolved_count} unresolved comments for document {doc_id}")
            return unresolved_count
            
        except Exception as e:
            print(f"Error getting comment count: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to get comment count: {str(e)}"
            )

    def get_document_comments(self, doc_id: str, include_deleted: bool = False) -> list:
        """
        Get comments for a specific document using Google API library
        """
        try:
            print(f"Getting comments for document {doc_id}")
            
            # Use the drive service to get comments - added quotedFileContent to fields
            comments_response = self.drive_service.comments().list(
                fileId=doc_id,
                fields="comments(id,content,author,createdTime,modifiedTime,resolved,quotedFileContent)",
                includeDeleted=include_deleted,
                pageSize=100
            ).execute()
            
            # Filter for unresolved comments
            comments = [comment for comment in comments_response.get('comments', []) 
                       if not comment.get('resolved', False)]
            
            processed_comments = []
            for comment in comments:
                # Extract quoted text if available
                quoted_text = None
                if 'quotedFileContent' in comment:
                    quoted_text = comment['quotedFileContent'].get('value')
                
                processed_comment = {
                    'id': comment['id'],
                    'content': comment.get('content', ''),
                    'author': {
                        'displayName': comment.get('author', {}).get('displayName', 'Unknown'),
                        'email': comment.get('author', {}).get('emailAddress', None),
                        'photoLink': comment.get('author', {}).get('photoLink', None)
                    },
                    'createdTime': comment.get('createdTime'),
                    'modifiedTime': comment.get('modifiedTime'),
                    'resolved': False,
                    'quotedText': quoted_text
                }
                
                processed_comments.append(processed_comment)
            
            print(f"Found {len(processed_comments)} unresolved comments for document {doc_id}")
            return processed_comments
            
        except Exception as e:
            print(f"Error getting comments: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to get comments: {str(e)}"
            )

    async def download_doc(self, doc_id: str) -> str:
        """Download a Google Doc in its original format (markdown or PDF)"""
        try:
            print(f"Downloading document with ID: {doc_id}")
            
            # Get current user info and check role
            user_info = await get_client()
            if not user_info.get("success"):
                raise HTTPException(
                    status_code=401,
                    detail="Unable to get user information"
                )
            
            # Check if user has admin or teacher role
            user_role = user_info["user"].get("role")
            if user_role not in ["admin", "teacher"]:
                raise HTTPException(
                    status_code=403,
                    detail="Only admin and teacher roles can download documents"
                )
            
            # Create uploads directory if it doesn't exist
            upload_dir = 'uploads'
            os.makedirs(upload_dir, exist_ok=True)
            
            # Get document type from Supabase - no need for service role
            supabase = SupabaseDocumentOps.get_client()
            doc_result = supabase.table("documents")\
                .select("type")\
                .eq("google_doc_id", doc_id)\
                .single()\
                .execute()
                
            if not doc_result.data:
                raise HTTPException(
                    status_code=404,
                    detail=f"Document with ID '{doc_id}' not found"
                )
            
            # Update document with approver information
            supabase.table("documents")\
                .update({
                    "approved_by": user_info["user"]["id"],
                    "approved_by_email": user_info["user"]["email"],
                    "approved_by_username": user_info["user"]["username"],
                    "approved_at": datetime.utcnow().isoformat()
                })\
                .eq("google_doc_id", doc_id)\
                .execute()

            doc_type = doc_result.data['type']

            # Get the document title
            file = self.drive_service.files().get(
                fileId=doc_id,
                fields='name'
            ).execute()
            
            # Remove .md extension if it exists in the original name
            original_name = file['name'].replace('.md', '')
            # Create a safe filename
            safe_filename = re.sub(r'[^a-zA-Z0-9-_]', '_', original_name)
            
            if doc_type == 'MARKDOWN':
                # Export as plain text for markdown
                file_path = os.path.join(upload_dir, f"{safe_filename}.md")
                response = self.drive_service.files().export(
                    fileId=doc_id,
                    mimeType='text/plain'
                ).execute()
            else:
                # Export as PDF for other types
                file_path = os.path.join(upload_dir, f"{safe_filename}.pdf")
                response = self.drive_service.files().export(
                    fileId=doc_id,
                    mimeType='application/pdf'
                ).execute()
            
            # Write the file
            with open(file_path, 'wb') as f:
                f.write(response)
            
            print(f"Successfully downloaded document to {file_path}")
            return file_path
            
        except Exception as e:
            print(f"Error downloading document: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to download document: {str(e)}"
            )

    def export_document(self, doc_id: str, doc_type: str, upload_dir: str) -> str:
        """Export a document to the specified directory"""
        os.makedirs(upload_dir, exist_ok=True)
        file_path, response = export_file(self.drive_service, doc_id, doc_type)
        full_path = os.path.join(upload_dir, os.path.basename(file_path))
        
        with open(full_path, 'wb') as f:
            f.write(response)
            
        return full_path
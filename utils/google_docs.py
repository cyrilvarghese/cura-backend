import os
from google.oauth2 import service_account
from googleapiclient.discovery import build
from fastapi import HTTPException
from typing import Optional, List, Dict, Any, Tuple
import re
import sqlite3
import requests

SCOPES = ['https://www.googleapis.com/auth/drive.file']
# SERVICE_ACCOUNT_FILE = 'utils/service-account-key.json'
print("File exists:", os.path.exists('/etc/secrets/service-account-key'))
SERVICE_ACCOUNT_FILE = '/etc/secrets/service-account-key'
FOLDER_NAME = 'cases-for-review'

class GoogleDocsManager:
    def __init__(self):
        try:
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

    def _get_or_create_folder(self) -> str:
        """Get the folder ID if it exists, or create it if it doesn't"""
        try:
            print(f"Searching for folder: {FOLDER_NAME}")
            # Search for the folder
            results = self.drive_service.files().list(
                q=f"name='{FOLDER_NAME}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
                spaces='drive',
                fields='files(id, name)'
            ).execute()
            
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
            
            folder = self.drive_service.files().create(
                body=folder_metadata,
                fields='id'
            ).execute()
            
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
            print(f"Creating new Google Doc with title: {title}")
            # Create an empty doc in the folder
            doc_body = {
                'name': title,
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
            print(f"Error creating Google Doc: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to create Google Doc: {str(e)}"
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

    def list_folder_files(self) -> list:
        """List all files in the designated folder with their status"""
        try:
            print(f"Listing files in folder ID: {self.folder_id}")
            
            # Use Drive API service to list files
            results = self.drive_service.files().list(
                q=f"'{self.folder_id}' in parents and trashed=false",
                pageSize=100,
                orderBy="modifiedTime desc",
                fields="files(id, name, webViewLink, createdTime, modifiedTime)"
            ).execute()
            
            files = results.get('files', [])
            
            if not files:
                print("No files found in the folder.")
                return []
            
            # Get database connection to fetch status
            conn = sqlite3.connect('medical_assessment.db')
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Process files and add status
            for file in files:
                try:
                    # Get status from documents table
                    cursor.execute('''
                        SELECT status 
                        FROM documents 
                        WHERE google_doc_id = ?
                    ''', (file['id'],))
                    
                    doc_status = cursor.fetchone()
                    file['status'] = doc_status['status'] if doc_status else 'CASE_REVIEW_PENDING'
                    file['commentCount'] = 0  # Default to 0 since we're not counting anymore
                    
                except Exception as error:
                    print(f"Error processing file {file['id']}: {str(error)}")
                    file['status'] = 'CASE_REVIEW_PENDING'
                    file['commentCount'] = 0
            
            conn.close()
            print(f"Found {len(files)} files in the folder")
            return files
            
        except Exception as e:
            print(f"Error listing files in folder: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to list files in folder: {str(e)}")

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

    def delete_doc(self, doc_id: str) -> bool:
        """Delete a Google Doc and its database record"""
        try:
            print(f"Deleting document with ID: {doc_id}")
            
            # First delete from Google Drive
            self.drive_service.files().delete(fileId=doc_id).execute()
            
            # Then delete from our database
            conn = sqlite3.connect('medical_assessment.db')
            cursor = conn.cursor()
            
            # Delete from documents table
            cursor.execute('''
                DELETE FROM documents 
                WHERE google_doc_id = ?
            ''', (doc_id,))
            
            # Delete from topic_documents table
            cursor.execute('''
                DELETE FROM topic_documents 
                WHERE document_id IN (
                    SELECT id FROM documents WHERE google_doc_id = ?
                )
            ''', (doc_id,))
            
            conn.commit()
            conn.close()
            
            print(f"Successfully deleted document {doc_id}")
            return True
            
        except Exception as e:
            print(f"Error deleting document: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to delete document: {str(e)}"
            )
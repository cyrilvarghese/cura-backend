import os
import re

def export_file(drive_service, doc_id: str, doc_type: str = 'PDF') -> tuple[str, bytes]:
    """Export a file from Google Drive"""
    # Get the document title
    file = drive_service.files().get(
        fileId=doc_id,
        fields='name'
    ).execute()
    
    # Remove .md extension if it exists in the original name
    original_name = file['name'].replace('.md', '')
    # Create a safe filename
    safe_filename = re.sub(r'[^a-zA-Z0-9-_]', '_', original_name)
    
    if doc_type == 'MARKDOWN':
        # Export as plain text for markdown
        file_path = os.path.join('uploads', f"{safe_filename}.md")
        response = drive_service.files().export(
            fileId=doc_id,
            mimeType='text/plain'
        ).execute()
    else:
        # Export as PDF for other types
        file_path = os.path.join('uploads', f"{safe_filename}.pdf")
        response = drive_service.files().export(
            fileId=doc_id,
            mimeType='application/pdf'
        ).execute()
    
    return file_path, response 
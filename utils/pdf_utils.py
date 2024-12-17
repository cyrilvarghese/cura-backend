from fastapi import HTTPException
import pdftotext
import io

def extract_text_from_document(file) -> str:
    """Extract text from a PDF or Markdown file."""
    try:
        # Get file extension
        filename = file.filename.lower()
        
        # Handle markdown files
        if filename.endswith('.md'):
            content = file.file.read().decode('utf-8')
            return content.strip()
            
        # Handle PDF files
        elif filename.endswith('.pdf'):
            pdf_bytes = file.file.read()
            pdf = pdftotext.PDF(io.BytesIO(pdf_bytes))
            text = "\n".join(pdf)
            return " ".join(text.split()).strip()
            
        else:
            raise HTTPException(
                status_code=400,
                detail="Unsupported file format. Only .pdf and .md files are supported."
            )
            
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error reading file: {str(e)}"
        )
    finally:
        # Reset file pointer for potential future reads
        file.file.seek(0)

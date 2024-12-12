from fastapi import HTTPException
import pdftotext
import io

def extract_text_from_pdf(pdf_file) -> str:
    """Extract text from a PDF file using pdftotext."""
    try:
        # Read the UploadFile into bytes
        pdf_bytes = pdf_file.file.read()
        
        # Load PDF using pdftotext
        pdf = pdftotext.PDF(io.BytesIO(pdf_bytes))
        
        # Extract text from all pages and join with proper spacing
        text = "\n".join(pdf)
        
        # Clean up the text
        cleaned_text = " ".join(text.split())
        
        return cleaned_text.strip()
        
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Error reading PDF file: {str(e)}"
        )
    finally:
        # Reset file pointer for potential future reads
        pdf_file.file.seek(0) 
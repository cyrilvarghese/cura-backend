from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from pathlib import Path
import os

markdown_router = APIRouter(
    prefix="/markdown",
    tags=["markdown"]
)

class MarkdownContent(BaseModel):
    content: str
    filename: str

@markdown_router.post("/save")
async def save_markdown(markdown: MarkdownContent):
    try:
        # Create markdown directory if it doesn't exist
        base_path = Path("markdown-files")
        base_path.mkdir(exist_ok=True)
        
        # Ensure filename ends with .md
        if not markdown.filename.endswith('.md'):
            markdown.filename += '.md'
            
        file_path = base_path / markdown.filename
        
        # Write content to file
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(markdown.content)
            
        return {
            "message": "Markdown saved successfully",
            "file_path": str(file_path)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save markdown: {str(e)}"
        ) 
from typing import Optional
from fastapi import APIRouter, HTTPException, Form
from datetime import datetime
import uuid
import os
from dotenv import load_dotenv
from pathlib import Path
import json
import re
import asyncio
import google.generativeai as genai
from utils.pdf_utils import extract_text_from_document
from utils.text_cleaner import clean_code_block
from pydantic import BaseModel

# Load environment variables
load_dotenv()

# Configure Gemini
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

router = APIRouter(
    prefix="/history_context",
    tags=["create-data"]
)

def load_prompt(file_path: str) -> str:
    """Load the prompt from a specified file."""
    try:
        with open(file_path, 'r') as file:
            return file.read()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Prompt file not found.")

class CreateHistoryContextRequest(BaseModel):
    file_name: str
    case_id: Optional[int] = None

@router.post("/create")
async def create_history_context(request: CreateHistoryContextRequest):
    """
    Create history context data based on a case document.
    Extracts a history summary and expected questions using Gemini AI.
    """
    try:
        print(f"[{datetime.now()}] Starting history context creation for file: {request.file_name}, case_id: {request.case_id}")
        
        # Get the uploads directory path
        uploads_dir = Path(os.getenv("UPLOADS_DIR", "case-data/uploads"))
        
        # Convert the incoming filename to a safe version
        filename = re.sub(r'[^a-zA-Z0-9-_.]', '_', request.file_name)
        
        # Construct the full file path in the uploads directory
        file_path = uploads_dir / filename

        print(f"[{datetime.now()}] Attempting to read file from: {file_path}")

        if not file_path.exists():
            print(f"[{datetime.now()}] ❌ File not found: {file_path}")
            raise HTTPException(status_code=404, detail=f"File not found in uploads directory: {filename}")

        class FileWrapper:
            def __init__(self, filepath):
                self.filename = Path(filepath).name
                self.file = open(filepath, 'rb')

        try:
            file_wrapper = FileWrapper(file_path)
            case_document = extract_text_from_document(file_wrapper)
            file_wrapper.file.close()
            print(f"[{datetime.now()}] ✅ Successfully extracted text from document")
        except IOError as e:
            print(f"[{datetime.now()}] ❌ Failed to read file: {str(e)}")
            raise HTTPException(status_code=400, detail=f"Failed to read file: {str(e)}")

        print(f"[{datetime.now()}] Loading prompt...")
        prompt = load_prompt("prompts/gen_case_smry_for_hist.txt")
        
        # Format the prompt with the case document
        formatted_prompt = prompt.format(full_case_document=case_document)
        
        print(f"[{datetime.now()}] Calling Gemini model...")
        
        # Configure Gemini model
        model = genai.GenerativeModel('gemini-2.0-flash')
        generation_config = {
            "temperature": 0.7,
            "top_p": 0.8,
            "top_k": 40
        }
        
        # Generate content using Gemini
        content = {
            "contents": [
                {
                    "parts": [
                        {"text": formatted_prompt}
                    ]
                }
            ],
            "generation_config": generation_config
        }
        
        response = await asyncio.to_thread(model.generate_content, **content)
        print(f"[{datetime.now()}] ✅ Received response from Gemini model")
        
        # Process and clean the response
        print(f"[{datetime.now()}] Processing Gemini response...")
        cleaned_json = clean_code_block(response.text)
        
        try:
            # Parse the JSON response
            history_context = json.loads(cleaned_json)
            print(f"[{datetime.now()}] ✅ Successfully parsed JSON response")
            
            # Save the data to file
            case_dir = Path(f"case-data/case{request.case_id}")
            case_dir.mkdir(parents=True, exist_ok=True)
            
            output_file = case_dir / "history_context.json"
            with open(output_file, 'w') as f:
                json.dump(history_context, f, indent=2)
            
            print(f"[{datetime.now()}] ✅ Saved history context to {output_file}")
            
            # Format response
            formatted_response = {
                "case_id": request.case_id,
                "content": history_context,
                "file_path": str(output_file),
                "timestamp": datetime.now().isoformat(),
                "type": "ai"
            }
            
            return formatted_response
        
        except json.JSONDecodeError as e:
            print(f"[{datetime.now()}] ❌ Failed to parse JSON: {str(e)}")
            print(f"Raw response: {response.text}")
            raise HTTPException(status_code=500, detail=f"Invalid JSON response from Gemini: {str(e)}")
        
    except Exception as e:
        error_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{error_timestamp}] ❌ Error in create_history_context: {str(e)}")
        print(f"[{error_timestamp}] ❌ Error type: {type(e).__name__}")
        print(f"[{error_timestamp}] ❌ Error details: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) 
from typing import Optional
from fastapi import APIRouter, HTTPException, Form, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
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
from auth.auth_api import get_user_from_token

# Load environment variables
load_dotenv()

# Configure Gemini
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

# Define the security scheme
security = HTTPBearer()

router = APIRouter(
    prefix="/clinical_findings_context",
    tags=["create-data"]
)

def load_prompt(file_path: str) -> str:
    """Load the prompt from a specified file."""
    try:
        with open(file_path, 'r') as file:
            return file.read()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Prompt file not found.")

class CreateClinicalFindingsRequest(BaseModel):
    file_name: str
    case_id: Optional[int] = None

@router.post("/create")
async def create_clinical_findings(
    request: CreateClinicalFindingsRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Create clinical findings data based on a case document.
    """
    print(f"[{datetime.now()}] Starting clinical findings creation for file: {request.file_name}, case_id: {request.case_id}")
    
    # Extract token and authenticate the user
    try:
        token = credentials.credentials  # This is the raw JWT
        print(f"[DEBUG] Extracted JWT: {token}")
        
        print(f"[CLINICAL_FINDINGS] 🔐 Authenticating user...")
        user_response = await get_user_from_token(token)
        if not user_response["success"]:
            error_message = user_response.get("error", "Authentication required")
            print(f"[CLINICAL_FINDINGS] ❌ Authentication failed: {error_message}")
            raise HTTPException(status_code=401, detail=error_message)
        
        user_id = user_response["user"]["id"]
        user_role = user_response["user"].get("role", "")
        
        # Check if user is admin or teacher
        if user_role not in ["admin", "teacher"]:
            print(f"[CLINICAL_FINDINGS] ❌ Access denied: User role '{user_role}' is not authorized")
            raise HTTPException(status_code=403, detail="Only teachers and admins can create clinical findings")
            
        print(f"[CLINICAL_FINDINGS] ✅ User authenticated successfully. User ID: {user_id}, Role: {user_role}")
    except HTTPException as auth_error:
        print(f"[CLINICAL_FINDINGS] ❌ HTTP exception during authentication: {str(auth_error)}")
        raise auth_error
    except Exception as auth_error:
        print(f"[CLINICAL_FINDINGS] ❌ Unexpected error during authentication: {str(auth_error)}")
        raise HTTPException(status_code=401, detail="Authentication failed")

    try:
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
        prompt = load_prompt("prompts/gen_clinical_findings_context_v2.txt")
        
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
            clinical_findings_context = json.loads(cleaned_json)
            print(f"[{datetime.now()}] ✅ Successfully parsed JSON response")
            
            # Save the data to file
            case_dir = Path(f"case-data/case{request.case_id}")
            case_dir.mkdir(parents=True, exist_ok=True)
            
            output_file = case_dir / "clinical_findings_context.json"
            with open(output_file, 'w') as f:
                json.dump(clinical_findings_context, f, indent=2)
            
            print(f"[{datetime.now()}] ✅ Saved clinical findings context to {output_file}")
            
            # Format response
            formatted_response = {
                "case_id": request.case_id,
                "content": clinical_findings_context,
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
        print(f"[{error_timestamp}] ❌ Error in create_clinical_findings_context: {str(e)}")
        print(f"[{error_timestamp}] ❌ Error type: {type(e).__name__}")
        print(f"[{error_timestamp}] ❌ Error details: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) 
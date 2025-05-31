from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from datetime import datetime
from pathlib import Path
import json
import os
import google.generativeai as genai
import asyncio
from typing import List, Dict, Any, Optional
from utils.text_cleaner import clean_code_block
from utils.session_manager import SessionManager
from auth.auth_api import get_user, get_user_from_token

# Define the security scheme
security = HTTPBearer()

# Initialize the router
router = APIRouter(
    prefix="/osce",
    tags=["osce-generator"]
)

# Initialize Gemini client
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

# Initialize session manager
session_manager = SessionManager()

class OSCERequest(BaseModel):
    case_id: str

    class Config:
        json_schema_extra = {
            "example": {
                "case_id": "16"
            }
        }

def load_prompt(file_path: str) -> str:
    """Load the prompt from a specified file."""
    try:
        with open(file_path, 'r') as file:
            return file.read()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Prompt file not found: {file_path}")

async def load_case_doc(case_id: str) -> str:
    """Load the case document for the specified case."""
    try:
        file_path = Path(f"case-data/case{case_id}/case_doc.txt")
        if not file_path.exists():
            raise FileNotFoundError(f"Case document not found for case {case_id}")
        
        with open(file_path, 'r') as file:
            return file.read()
    except Exception as e:
        raise HTTPException(
            status_code=404, 
            detail=f"Failed to load case document for case {case_id}: {str(e)}"
        )

async def get_department(case_id: str) -> str:
    """Get the department from the case cover file."""
    try:
        file_path = Path(f"case-data/case{case_id}/case_cover.json")
        if not file_path.exists():
            raise FileNotFoundError(f"Cover file not found for case {case_id}")
        
        with open(file_path, 'r') as file:
            cover_data = json.load(file)
            return cover_data.get("department", "General Medicine")
    except Exception as e:
        print(f"Error loading department: {str(e)}")
        return "General Medicine"  # Default fallback

# Load the OSCE generator prompt
OSCE_PROMPT = load_prompt("prompts/OSCE-gen3.md")
print(f"OSCE_PROMPT: {OSCE_PROMPT[:200]}")

@router.post("/generate")
async def generate_osce(
    osce_data: dict,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Generate OSCE content for a case.
    """
    print(f"[OSCE_GENERATOR] 📝 Generating OSCE with data: {osce_data}")
    
    # Extract token and authenticate the user
    try:
        token = credentials.credentials
        print(f"[DEBUG] Extracted JWT: {token}")
        
        print(f"[OSCE_GENERATOR] 🔐 Authenticating user...")
        user_response = await get_user_from_token(token)
        if not user_response["success"]:
            error_message = user_response.get("error", "Authentication required")
            print(f"[OSCE_GENERATOR] ❌ Authentication failed: {error_message}")
            raise HTTPException(status_code=401, detail=error_message)
        
        user_id = user_response["user"]["id"]
        user_role = user_response["user"].get("role", "")
        
        # Check if user is admin or teacher
        if user_role not in ["admin", "teacher"]:
            print(f"[OSCE_GENERATOR] ❌ Access denied: User role '{user_role}' is not authorized")
            raise HTTPException(status_code=403, detail="Only teachers and admins can generate OSCE content")
            
        print(f"[OSCE_GENERATOR] ✅ User authenticated successfully. User ID: {user_id}, Role: {user_role}")
        
        try:
            print(f"\n[{datetime.now()}] 🔍 Starting OSCE question generation for case {osce_data['case_id']}")
            
            # Load required data
            case_doc = await load_case_doc(osce_data['case_id'])
            department = await get_department(osce_data['case_id'])
            
            # Get student session data
            session_data = session_manager.get_session(user_id, osce_data['case_id'])
            if not session_data:
                raise HTTPException(status_code=404, detail="No session data found for this case")
            
            # Configure the model
            model = genai.GenerativeModel('gemini-2.0-flash')
            generation_config = {
                "temperature": 0.7,
                "top_p": 0.8,
                "top_k": 40
            }
            
            # Format the prompt with the required data
            formatted_prompt = OSCE_PROMPT.format(
                case_markdown=case_doc,
                student_session_json=json.dumps(session_data, indent=2),
                department=department
            )
            
            # Prepare the content for generation
            content = {
                "contents": [{"parts": [{"text": formatted_prompt}]}],
                "generation_config": generation_config
            }
            
            start_time = datetime.now()
            
            # Generate the OSCE questions
            print("[DEBUG] Sending prompt to Gemini model...")
            response = await asyncio.to_thread(model.generate_content, **content)
            print("[DEBUG] Received response from Gemini model")
            
            # Process the response content
            response_content = response.text
            print(f"[DEBUG] Raw response content: {response_content[:100]}...")
            
            # Clean and parse the response
            try:
                cleaned_content = clean_code_block(response_content)
                osce_questions = json.loads(cleaned_content)
            except json.JSONDecodeError as je:
                print(f"[DEBUG] JSON parse error: {str(je)}")
                raise HTTPException(status_code=400, detail=f"Failed to parse model response: {str(je)}")
            
            end_time = datetime.now()
            processing_time = (end_time - start_time).total_seconds()
            
            # Prepare the response data
            response_data = {
                "case_id": osce_data['case_id'],
                "student_id": user_id,
                "department": department,
                "timestamp": datetime.now().isoformat(),
                "osce_questions": osce_questions,
                "metadata": {
                    "processing_time_seconds": processing_time,
                    "model_version": model.model_name,
                    "generation_config": generation_config
                }
            }
            
            print(f"[{datetime.now()}] ✅ Successfully generated OSCE questions")
            return response_data
        except Exception as e:
            print(f"[OSCE_GENERATOR] ❌ Error generating OSCE content: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error generating OSCE content: {str(e)}")
            
    except HTTPException as auth_error:
        print(f"[OSCE_GENERATOR] ❌ HTTP exception during authentication: {str(auth_error)}")
        raise auth_error
    except Exception as auth_error:
        print(f"[OSCE_GENERATOR] ❌ Unexpected error during authentication: {str(auth_error)}")
        raise HTTPException(status_code=401, detail="Authentication failed") 
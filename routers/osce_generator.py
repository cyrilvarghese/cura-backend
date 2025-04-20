from fastapi import APIRouter, HTTPException
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
from auth.auth_api import get_user

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
        file_path = Path(f"case-data/case{case_id}/cover.json")
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
async def generate_osce_questions(request: OSCERequest):
    """Generate OSCE questions based on case document and student session."""
    # First handle authentication outside main try block
    try:
        user_response = await get_user()
        if not user_response["success"]:
            error_message = user_response.get("error", "Authentication required")
            raise HTTPException(status_code=401, detail=error_message)
        student_id = user_response["user"]["id"]
    except HTTPException as auth_error:
        raise auth_error
    except Exception as auth_error:
        raise HTTPException(status_code=401, detail="Authentication failed")

    try:
        print(f"\n[{datetime.now()}] 🔍 Starting OSCE question generation for case {request.case_id}")
        
        # Load required data
        case_doc = await load_case_doc(request.case_id)
        department = await get_department(request.case_id)
        
        # Get student session data
        session_data = session_manager.get_session(student_id, request.case_id)
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
            "case_id": request.case_id,
            "student_id": student_id,
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

    except HTTPException as http_error:
        # Re-raise HTTP exceptions directly
        raise http_error
    except Exception as e:
        error_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{error_timestamp}] ❌ Error in generate_osce_questions: {str(e)}")
        print(f"[DEBUG] Error type: {type(e).__name__}")
        print(f"[DEBUG] Full error details: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail="An unexpected error occurred while generating OSCE questions"
        ) 
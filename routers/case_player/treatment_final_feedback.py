from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException
from datetime import datetime
import os
from dotenv import load_dotenv
import json
from pathlib import Path
import google.generativeai as genai
from utils.text_cleaner import clean_code_block
from utils.session_manager import SessionManager
from auth.auth_api import get_user
import asyncio

# Load environment variables
load_dotenv()

# Constants
CASE_DATA_PATH_PATTERN = "case-data/case{}"
TREATMENT_CONTEXT_FILENAME = "treatment_context.json"
HISTORY_CONTEXT_FILENAME = "history_context.json"

router = APIRouter(
    prefix="/treatment-protocol-feedback",
    tags=["treatment-protocol-feedback"]
)

# Initialize the Gemini client and SessionManager
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
session_manager = SessionManager()

def load_prompt(file_path: str) -> str:
    """Load the prompt from a specified file."""
    try:
        with open(file_path, 'r') as file:
            return file.read()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Prompt file not found: {file_path}")

# Load the prompt from file
TREATMENT_FINAL_FEEDBACK_PROMPT = load_prompt("prompts/treatment_final_feedback.txt")

async def load_treatment_context(case_id: int) -> Dict[str, Any]:
    """Load the treatment context from the case file."""
    try:
        file_path = Path(f"{CASE_DATA_PATH_PATTERN.format(case_id)}/{TREATMENT_CONTEXT_FILENAME}")
        if not file_path.exists():
            raise FileNotFoundError(f"Treatment context not found for case {case_id}")
        
        with open(file_path, 'r') as file:
            return json.load(file)
    except Exception as e:
        raise HTTPException(
            status_code=404, 
            detail=f"Failed to load treatment context for case {case_id}: {str(e)}"
        )

async def load_history_context(case_id: int) -> Dict[str, Any]:
    """Load the history context from the case file."""
    try:
        file_path = Path(f"{CASE_DATA_PATH_PATTERN.format(case_id)}/{HISTORY_CONTEXT_FILENAME}")
        if not file_path.exists():
            raise FileNotFoundError(f"History context not found for case {case_id}")
        
        with open(file_path, 'r') as file:
            return json.load(file)
    except Exception as e:
        raise HTTPException(
            status_code=404, 
            detail=f"Failed to load history context for case {case_id}: {str(e)}"
        )

async def get_session_data():
    """Helper function to get authenticated user's session data."""
    # Get session from authenticated user
    user_response = await get_user()
    if not user_response["success"]:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    student_id = user_response["user"]["id"]
    session_data = session_manager.get_session(student_id)
    if not session_data:
        raise HTTPException(status_code=404, detail="No active session found")
    
    return student_id, session_data

async def save_feedback_response(case_id: str, response_data: dict) -> dict:
    """Save the feedback response to a file."""
    try:
        # Create directory if it doesn't exist
        output_dir = Path(f"case-data/case{case_id}/feedback")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate a filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = output_dir / f"treatment_final_feedback_{timestamp}.json"
        
        # Save the response to the file
        with open(file_path, 'w') as f:
            json.dump(response_data, f, indent=2)
        
        return {"status": "success", "file_path": str(file_path)}
    except Exception as e:
        print(f"Error saving feedback response: {e}")
        return {"status": "error", "message": str(e)}

@router.get("/final")
async def get_treatment_final_feedback():
    """Generate comprehensive feedback on student's drug treatment plan."""
    try:
        print(f"\n[{datetime.now()}] 🔍 Starting treatment final feedback generation")
        
        # Get session data from authenticated user
        student_id, session_data = await get_session_data()
        case_id = session_data["case_id"]
        
        # Load context data
        treatment_context = await load_treatment_context(int(case_id))
        history_context = await load_history_context(int(case_id))
        
        # Configure the model
        model = genai.GenerativeModel('gemini-2.0-flash')
        generation_config = {
            "temperature": 0.7,
            "top_p": 0.8,
            "top_k": 40
        }
        
        # Format the prompt with the required data
        formatted_prompt_params = {
            "treatment_context_json": json.dumps(treatment_context, indent=2),
            "session_data_json": json.dumps(session_data, indent=2)
        }
        
        # Add history context
        formatted_prompt_params["history_context_json"] = json.dumps(history_context, indent=2)
        
        formatted_prompt = TREATMENT_FINAL_FEEDBACK_PROMPT.format(**formatted_prompt_params)
        
        # Generate the feedback
        start_time = datetime.now()
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
        
        print("[DEBUG] Sending prompt to Gemini model...")
        response = await asyncio.to_thread(model.generate_content, **content)
        print("[DEBUG] Received response from Gemini model")
        
        # Process the response
        cleaned_content = clean_code_block(response.text)
        feedback_result = json.loads(cleaned_content)
        
        # Save feedback to session
        try:
            session_manager.add_treatment_feedback(
                student_id=student_id,
                feedback_result=feedback_result
            )
            print(f"[DEBUG] Successfully saved treatment final feedback to session")
        except Exception as save_error:
            print(f"[WARNING] Failed to save treatment final feedback to session: {str(save_error)}")
        
        # Create the response data
        response_data = {
            "case_id": case_id,
            "student_id": student_id,
            "timestamp": datetime.now().isoformat(),
            "feedback_result": feedback_result,
            "metadata": {
                "processing_time_seconds": (datetime.now() - start_time).total_seconds(),
                "model_version": "gemini-2.0-flash",
                "feedback_type": "treatment_final"
            }
        }
        
        # Save to file
        save_result = await save_feedback_response(case_id, response_data)
        if save_result["status"] == "success":
            response_data["file_path"] = save_result["file_path"]
        
        print(f"[{datetime.now()}] ✅ Successfully generated treatment final feedback")
        return response_data
        
    except json.JSONDecodeError as e:
        error_msg = f"Error parsing JSON response: {str(e)}"
        print(f"[{datetime.now()}] ❌ {error_msg}")
        raise HTTPException(status_code=400, detail=error_msg)
    except Exception as e:
        error_msg = f"Error in get_treatment_final_feedback: {str(e)}"
        print(f"[{datetime.now()}] ❌ {error_msg}")
        raise HTTPException(status_code=500, detail=error_msg) 
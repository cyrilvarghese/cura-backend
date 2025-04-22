from typing import List, Dict, Any
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

router = APIRouter(
    prefix="/feedback",
    tags=["history-feedback"]
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
HISTORY_FEEDBACK_PROMPT = load_prompt("prompts/history_feedback2.txt")

async def load_case_context(case_id: int) -> str:
    """Load the case context from the case file."""
    try:
        file_path = Path(f"case-data/case{case_id}/case_doc.txt")
        if not file_path.exists():
            raise FileNotFoundError(f"Case document not found for case {case_id}")
        
        with open(file_path, 'r') as file:
            return file.read()
    except Exception as e:
        raise HTTPException(
            status_code=404, 
            detail=f"Failed to load context for case {case_id}: {str(e)}"
        )

async def load_expected_questions(case_id: int) -> List[str]:
    """Load the expected questions from the history context file."""
    try:
        file_path = Path(f"case-data/case{case_id}/history_context.json")
        if not file_path.exists():
            raise FileNotFoundError(f"History context not found for case {case_id}")
        
        with open(file_path, 'r') as file:
            return json.load(file)
    except Exception as e:
        raise HTTPException(
            status_code=404,
            detail=f"Failed to load expected questions for case {case_id}: {str(e)}"
        )

@router.get("/history-taking")
async def get_history_feedback():
    """Generate feedback for history taking using Gemini."""
    try:
        print(f"\n[{datetime.now()}] 🔍 Starting history feedback generation")
        
        # Get current user
        user_response = await get_user()
        if not user_response["success"]:
            raise HTTPException(status_code=401, detail="Authentication required")
        
        student_id = user_response["user"]["id"]
        print(f"[DEBUG] Authenticated student ID: {student_id}")
        
        # Get student's session data
        print("[DEBUG] Getting student session data...")
        session_data = session_manager.get_session(student_id)
        if not session_data:
            raise HTTPException(status_code=404, detail="No active session found")
        
        case_id = session_data["case_id"]
        print(f"[DEBUG] Found case ID from session: {case_id}")
        
        # Load the case context
        print("[DEBUG] Attempting to load case context...")
        context = await load_case_context(int(case_id))
        print(f"[DEBUG] Successfully loaded context length: {len(context)}")
        
        # Load expected questions
        print("[DEBUG] Loading expected questions...")
        expected_questions = await load_expected_questions(int(case_id))
        print(f"[DEBUG] Loaded {len(expected_questions)} expected questions")
        
        student_questions = []
        for interaction in session_data["interactions"]["history_taking"]:
            student_questions.append({
                "question": interaction["question"],
                "response": interaction["response"]
            })
        
        # Configure the model
        model = genai.GenerativeModel('gemini-2.0-flash')
        generation_config = {
            "temperature": 0.7,
            "top_p": 0.8,
            "top_k": 40
        }
        
        # Format the prompt with the required data
        formatted_prompt = HISTORY_FEEDBACK_PROMPT.format(
            case_context=context,
            expected_questions=json.dumps(expected_questions, indent=2),
            student_questions=json.dumps(student_questions, indent=2)
        )
        
        # Prepare the content for generation
        content = {
            "contents": [{"parts": [{"text": formatted_prompt}]}],
            "generation_config": generation_config
        }
        
        start_time = datetime.now()
        
        # Generate the feedback
        print("[DEBUG] Sending prompt to Gemini model...")
        response = await asyncio.to_thread(model.generate_content, **content)
        print("[DEBUG] Received response from Gemini model")
        
        # Process the response content
        response_content = response.text
        print(f"[DEBUG] Raw response content: {response_content[:100]}...")
        
        # Clean the response and parse as JSON
        try:
            cleaned_content = clean_code_block(response_content)
            print(f"[DEBUG] Cleaned content: {cleaned_content[:200]}...")
            feedback_result = json.loads(cleaned_content)
            print(f"[DEBUG] Parsed JSON result: {json.dumps(feedback_result, indent=2)}")
        except json.JSONDecodeError as je:
            print(f"[DEBUG] JSON parse error: {str(je)}")
            print(f"[DEBUG] Failed content: {cleaned_content}")
            feedback_result = {
                "error": "Failed to parse model response",
                "details": str(je)
            }
        
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        
        response_data = {
            "case_id": case_id,
            "student_id": student_id,
            "timestamp": datetime.now().isoformat(),
            "feedback": feedback_result,
            "metadata": {
                "processing_time_seconds": processing_time,
                "model_version": model.model_name,
                "generation_config": generation_config,
                "total_questions_analyzed": len(student_questions)
            }
        }
        
        print(f"[{datetime.now()}] ✅ Successfully generated history feedback")
        print(f"[DEBUG] Final response data: {json.dumps(response_data, indent=2)}")
        return response_data

    except json.JSONDecodeError as e:
        error_msg = f"[{datetime.now()}] ❌ JSON parsing error: {str(e)}\n"
        error_msg += f"[DEBUG] Failed JSON content: {response_content}\n"
        error_msg += f"[DEBUG] Exception details: {str(e)}"
        print(error_msg)
        raise HTTPException(status_code=400, detail=error_msg)
    except Exception as e:
        error_msg = f"[{datetime.now()}] ❌ Error in get_history_feedback:\n"
        error_msg += f"[DEBUG] Error type: {type(e).__name__}\n"
        error_msg += f"[DEBUG] Error message: {str(e)}\n"
        print(error_msg)
        raise HTTPException(status_code=500, detail=error_msg) 
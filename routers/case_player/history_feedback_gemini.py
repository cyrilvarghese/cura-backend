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

# Load the prompts from files
HISTORY_FEEDBACK_PROMPT = load_prompt("prompts/history_feedback2.txt")
HISTORY_ANALYSIS_PROMPT = load_prompt("prompts/history_analysis.txt")  # Prompt 1
HISTORY_AETCOM_PROMPT = load_prompt("prompts/history_aetcom.txt")      # Prompt 2

async def load_case_context(case_id: int) -> str:
    """Load the case context from the case file."""
    try:
        file_path = Path(f"case-data/case{case_id}/case_summary_history.txt")
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

async def get_session_data():
    """Helper function to get authenticated user's session data."""
    user_response = await get_user()
    if not user_response["success"]:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    student_id = user_response["user"]["id"]
    session_data = session_manager.get_session(student_id)
    if not session_data:
        raise HTTPException(status_code=404, detail="No active session found")
    
    return student_id, session_data

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
        
        response = await asyncio.to_thread(model.generate_content, **content)
        
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

@router.get("/history-taking/analysis")
async def get_history_analysis():
    """Step 1: Generate detailed analysis and overall score."""
    try:
        print(f"\n[{datetime.now()}] 🔍 Starting history analysis generation (Step 1)")
        
        # Get session data
        student_id, session_data = await get_session_data()
        case_id = session_data["case_id"]
        
        # Load required data
        context = await load_case_context(int(case_id))
        expected_questions = await load_expected_questions(int(case_id))
        
        # Get student questions
        student_questions = [
            {
                "question": interaction["question"],
                "response": interaction["response"]
            }
            for interaction in session_data["interactions"]["history_taking"]
        ]
        
        # Configure the model
        model = genai.GenerativeModel('gemini-2.0-flash')
        generation_config = {
            "temperature": 0.7,
            "top_p": 0.8,
            "top_k": 40
        }
        
        # Format the prompt with the required data
        formatted_prompt = HISTORY_ANALYSIS_PROMPT.format(
            case_context=context,
            expected_questions=json.dumps(expected_questions, indent=2),
            student_questions=json.dumps(student_questions, indent=2)
        )
        
        # Generate the analysis
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
        
        response = await asyncio.to_thread(model.generate_content, **content)
        
        # Process and return the response
        cleaned_content = clean_code_block(response.text)
        analysis_result = json.loads(cleaned_content)
        #add analysis_result to session
        session_manager.add_history_analysis(student_id, analysis_result)
        print(f"[DEBUG] Successfully saved analysis results to session")
        return {
            "case_id": case_id,
            "student_id": student_id,
            "timestamp": datetime.now().isoformat(),
            "analysis_result": analysis_result,
            "metadata": {
                "processing_time_seconds": (datetime.now() - start_time).total_seconds(),
                "model_version": model.model_name
            }
        }
        
    except Exception as e:
        error_msg = f"Error in get_history_analysis: {str(e)}"
        print(f"[{datetime.now()}] ❌ {error_msg}")
        raise HTTPException(status_code=500, detail=error_msg)

@router.get("/history-taking/aetcom")
async def get_history_aetcom_feedback():
    """Step 2: Generate domain scores and final feedback using analysis results."""
    try:
        print(f"\n[{datetime.now()}] 🔍 Starting AETCOM feedback generation (Step 2)")
        
        # Get session data
        student_id, session_data = await get_session_data()
        case_id = session_data["case_id"]
        
        # Get analysis results from session
        if "feedback" not in session_data["interactions"] or \
           "history_taking" not in session_data["interactions"]["feedback"] or \
           "analysis" not in session_data["interactions"]["feedback"]["history_taking"]:
            raise HTTPException(
                status_code=400,
                detail="Analysis results not found in session. Please run the analysis step first."
            )
            
        analysis_result = session_data["interactions"]["feedback"]["history_taking"]["analysis"]
       
        
        # Load required data
        context = await load_case_context(int(case_id))
        expected_questions = await load_expected_questions(int(case_id))
        
        # Get student questions
        student_questions = [
            {
                "question": interaction["question"],
                "response": interaction["response"]
            }
            for interaction in session_data["interactions"]["history_taking"]
        ]
        
        # Configure the model
        model = genai.GenerativeModel('gemini-2.0-flash')
        generation_config = {
            "temperature": 0.7,
            "top_p": 0.8,
            "top_k": 40
        }
        
        # Format the prompt with the required data
        formatted_prompt = HISTORY_AETCOM_PROMPT.format(
            case_context=context,
            expected_questions=json.dumps(expected_questions, indent=2),
            student_questions=json.dumps(student_questions, indent=2),
        )
        
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
        
        response = await asyncio.to_thread(model.generate_content, **content)
        
        # Process and return the response
        cleaned_content = clean_code_block(response.text)
        feedback_result = json.loads(cleaned_content)
        
        # Save both analysis and domain feedback to session
        try:
            session_manager.add_history_feedback(
                student_id=student_id,
                analysis_result=analysis_result,
                domain_feedback=feedback_result
            )
            print(f"[DEBUG] Successfully saved feedback results to session")
        except Exception as save_error:
            print(f"[WARNING] Failed to save feedback to session: {str(save_error)}")
        
        return {
            "case_id": case_id,
            "student_id": student_id,
            "timestamp": datetime.now().isoformat(),
            "feedback_result": feedback_result,
            "metadata": {
                "processing_time_seconds": (datetime.now() - start_time).total_seconds(),
                "model_version": model.model_name
            }
        }
        
    except Exception as e:
        error_msg = f"Error in get_history_aetcom_feedback: {str(e)}"
        print(f"[{datetime.now()}] ❌ {error_msg}")
        raise HTTPException(status_code=500, detail=error_msg)
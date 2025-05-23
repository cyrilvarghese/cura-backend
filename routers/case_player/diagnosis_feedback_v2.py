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

# Constants
CASE_DATA_PATH_PATTERN = "case-data/case{}"
DIAGNOSIS_CONTEXT_FILENAME = "diagnosis_context.json"
HISTORY_CONTEXT_FILENAME = "history_context.json"

router = APIRouter(
    prefix="/feedback/v2",
    tags=["diagnosis-feedback-v2"]
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
PRIMARY_DIAGNOSIS_PROMPT = load_prompt("prompts/diagnosis_feedback_new1.txt")
DIFFERENTIAL_DIAGNOSIS_PROMPT = load_prompt("prompts/diagnosis_feedback_new2.txt")
EDUCATIONAL_CAPSULES_PROMPT = load_prompt("prompts/diagnosis_feedback_new3.txt")

async def load_diagnosis_context(case_id: int) -> Dict[str, Any]:
    """Load the diagnosis context from the case file."""
    try:
        file_path = Path(f"{CASE_DATA_PATH_PATTERN.format(case_id)}/{DIAGNOSIS_CONTEXT_FILENAME}")
        if not file_path.exists():
            raise FileNotFoundError(f"Diagnosis context not found for case {case_id}")
        
        with open(file_path, 'r') as file:
            return json.load(file)
    except Exception as e:
        raise HTTPException(
            status_code=404, 
            detail=f"Failed to load diagnosis context for case {case_id}: {str(e)}"
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
    user_response = await get_user()
    if not user_response["success"]:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    student_id = user_response["user"]["id"]
    session_data = session_manager.get_session(student_id)
    if not session_data:
        raise HTTPException(status_code=404, detail="No active session found")
    
    return student_id, session_data

def prepare_student_input(session_data: Dict[str, Any]) -> Dict[str, Any]:
    """Prepare student input data from session data for the diagnosis feedback prompt."""
    student_input = {
        "interactions": {
            "physical_examinations": session_data["interactions"]["physical_examinations"],
            "tests_ordered": session_data["interactions"]["tests_ordered"],
            "clinical_findings": session_data["interactions"]["clinical_findings"],
            "diagnosis_submission": session_data["interactions"]["diagnosis_submission"],
            "final_diagnosis": session_data["interactions"]["final_diagnosis"]
        }
    }
    
    return student_input

async def generate_feedback(prompt_template: str, diagnosis_context: Dict[str, Any], 
                     student_input: Dict[str, Any], history_context: Dict[str, Any] = None) -> Dict[str, Any]:
    """Generate feedback using the Gemini model."""
    # Configure the model
    model = genai.GenerativeModel('gemini-2.0-flash')
    generation_config = {
        "temperature": 0.7,
        "top_p": 0.8,
        "top_k": 40
    }
    
    # Format the prompt with the required data
    formatted_prompt_params = {
        "diagnosis_context_json": json.dumps(diagnosis_context, indent=2),
        "student_session_json": json.dumps(student_input, indent=2)
    }
    
    # Add history context if provided
    if history_context:
        formatted_prompt_params["history_context_json"] = json.dumps(history_context, indent=2)
    
    formatted_prompt = prompt_template.format(**formatted_prompt_params)
    
    # Generate the feedback
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
    
    # Process the response
    cleaned_content = clean_code_block(response.text)
    feedback_result = json.loads(cleaned_content)
    
    return feedback_result

@router.get("/primary-diagnosis")
async def get_primary_diagnosis_feedback():
    """Generate feedback on student's primary diagnosis."""
    try:
        print(f"\n[{datetime.now()}] 🔍 Starting primary diagnosis feedback generation")
        
        # Get session data
        student_id, session_data = await get_session_data()
        case_id = session_data["case_id"]
        
        # Load context data
        diagnosis_context = await load_diagnosis_context(int(case_id))
        history_context = await load_history_context(int(case_id))
        
        # Prepare student input data
        student_input = prepare_student_input(session_data)
        
        # Generate the feedback
        start_time = datetime.now()
        feedback_result = await generate_feedback(
            prompt_template=PRIMARY_DIAGNOSIS_PROMPT,
            diagnosis_context=diagnosis_context,
            student_input=student_input,
            history_context=history_context
        )
        
        # Save feedback to session
        try:
            session_manager.add_diagnosis_feedback(
                student_id=student_id,
                feedback_result={"primaryDiagnosis": feedback_result}
            )
            print(f"[DEBUG] Successfully saved primary diagnosis feedback to session")
        except Exception as save_error:
            print(f"[WARNING] Failed to save primary diagnosis feedback to session: {str(save_error)}")
        
        return {
            "case_id": case_id,
            "student_id": student_id,
            "timestamp": datetime.now().isoformat(),
            "feedback_result": feedback_result,
            "metadata": {
                "processing_time_seconds": (datetime.now() - start_time).total_seconds(),
                "model_version": "gemini-2.0-flash",
                "feedback_type": "primary_diagnosis"
            }
        }
        
    except Exception as e:
        error_msg = f"Error in get_primary_diagnosis_feedback: {str(e)}"
        print(f"[{datetime.now()}] ❌ {error_msg}")
        raise HTTPException(status_code=500, detail=error_msg)

@router.get("/differential-diagnosis")
async def get_differential_diagnosis_feedback():
    """Generate feedback on student's differential diagnoses."""
    try:
        print(f"\n[{datetime.now()}] 🔍 Starting differential diagnosis feedback generation")
        
        # Get session data
        student_id, session_data = await get_session_data()
        case_id = session_data["case_id"]
        
        # Load context data
        diagnosis_context = await load_diagnosis_context(int(case_id))
        history_context = await load_history_context(int(case_id))
        
        # Prepare student input data
        student_input = prepare_student_input(session_data)
        
        # Generate the feedback
        start_time = datetime.now()
        feedback_result = await generate_feedback(
            prompt_template=DIFFERENTIAL_DIAGNOSIS_PROMPT,
            diagnosis_context=diagnosis_context,
            student_input=student_input,
            history_context=history_context
        )
        
        # Save feedback to session
        try:
            # Use the session manager method to add feedback
            session_manager.add_diagnosis_feedback(
                student_id=student_id,
                feedback_result={"differentialDiagnosis": feedback_result}
            )
            print(f"[DEBUG] Successfully saved differential diagnosis feedback to session")
        except Exception as save_error:
            print(f"[WARNING] Failed to save differential diagnosis feedback to session: {str(save_error)}")
        
        return {
            "case_id": case_id,
            "student_id": student_id,
            "timestamp": datetime.now().isoformat(),
            "feedback_result": feedback_result,
            "metadata": {
                "processing_time_seconds": (datetime.now() - start_time).total_seconds(),
                "model_version": "gemini-2.0-flash",
                "feedback_type": "differential_diagnosis"
            }
        }
        
    except Exception as e:
        error_msg = f"Error in get_differential_diagnosis_feedback: {str(e)}"
        print(f"[{datetime.now()}] ❌ {error_msg}")
        raise HTTPException(status_code=500, detail=error_msg)

@router.get("/educational-resources")
async def get_educational_resources():
    """Generate educational resources for medical conditions."""
    try:
        print(f"\n[{datetime.now()}] 🔍 Starting educational resources generation")
        
        # Get session data
        student_id, session_data = await get_session_data()
        case_id = session_data["case_id"]
        
        # Load diagnosis context
        diagnosis_context = await load_diagnosis_context(int(case_id))
        
        # Generate the educational capsules
        start_time = datetime.now() 
        feedback_result = await generate_feedback(
            prompt_template=EDUCATIONAL_CAPSULES_PROMPT,
            diagnosis_context=diagnosis_context,
            student_input={"case_id": case_id}  # Only minimal info needed for educational capsules
        )
        
        # Save feedback to session
        try:
            session_manager.add_diagnosis_feedback(
                student_id=student_id,
                feedback_result={"educationalCapsules": feedback_result}
            )
            print(f"[DEBUG] Successfully saved educational capsules to session")
        except Exception as save_error:
            print(f"[WARNING] Failed to save educational capsules to session: {str(save_error)}")
        
        return {
            "case_id": case_id,
            "student_id": student_id,
            "timestamp": datetime.now().isoformat(),
            "feedback_result": feedback_result,
            "metadata": {
                "processing_time_seconds": (datetime.now() - start_time).total_seconds(),
                "model_version": "gemini-2.0-flash",
                "feedback_type": "educational_capsules"
            }
        }
        
    except Exception as e:
        error_msg = f"Error in get_educational_capsules: {str(e)}"
        print(f"[{datetime.now()}] ❌ {error_msg}")
        raise HTTPException(status_code=500, detail=error_msg) 
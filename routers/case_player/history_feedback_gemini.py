from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from datetime import datetime
import os
from dotenv import load_dotenv
import json
from pathlib import Path
import google.generativeai as genai
from utils.text_cleaner import clean_code_block
from utils.session_manager import SessionManager
from auth.auth_api import get_user, get_user_from_token
import asyncio

# Load environment variables
load_dotenv()

# Constants
CASE_DATA_PATH_PATTERN = "case-data/case{}"
HISTORY_CONTEXT_FILENAME = "history_context.json"

# Define the security scheme
security = HTTPBearer()

router = APIRouter(
    prefix="/history-feedback",
    tags=["case-player"]
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
HISTORY_ANALYSIS_PROMPT = load_prompt("prompts/history_analysis_v3.md")  # Prompt 1
HISTORY_AETCOM_PROMPT = load_prompt("prompts/history_aetcom.txt")      # Prompt 2

async def load_case_context(case_id: int) -> str:
    """Load the case context from the case file."""
    try:
        file_path = Path(f"{CASE_DATA_PATH_PATTERN.format(case_id)}/{HISTORY_CONTEXT_FILENAME}")
        if not file_path.exists():
            raise FileNotFoundError(f"Case document not found for case {case_id}")
        
        with open(file_path, 'r') as file:
            data = json.load(file)
            # Format the JSON as a more readable string for the LLM
            case_summary = data["case_summary_history"]
            formatted_text = ""
            
            for key, value in case_summary.items():
                if isinstance(value, dict):
                    formatted_text += f"\n{key.replace('_', ' ').title()}:\n"
                    for sub_key, sub_value in value.items():
                        if sub_value is not None:
                            formatted_text += f"  - {sub_key.replace('_', ' ').title()}: {sub_value}\n"
                elif isinstance(value, list):
                    formatted_text += f"\n{key.replace('_', ' ').title()}:\n"
                    for item in value:
                        formatted_text += f"  - {item}\n"
                else:
                    formatted_text += f"\n{key.replace('_', ' ').title()}: {value}\n"
            
            return formatted_text
    except Exception as e:
        raise HTTPException(
            status_code=404, 
            detail=f"Failed to load context for case {case_id}: {str(e)}"
        )

async def load_expected_questions(case_id: int) -> List[str]:
    """Load the expected questions from the history context file."""
    try:
        file_path = Path(f"{CASE_DATA_PATH_PATTERN.format(case_id)}/{HISTORY_CONTEXT_FILENAME}")
        if not file_path.exists():
            raise FileNotFoundError(f"History context not found for case {case_id}")
        
        with open(file_path, 'r') as file:
            data = json.load(file)
            # Extract just the expected_questions array from the JSON
            if "expected_questions_with_domains" in data:
                return data["expected_questions_with_domains"]
            else:
                raise ValueError("No 'expected_questions_with_domains' field found in history context file")
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
            expected_questions_with_domains=json.dumps(expected_questions, indent=2),
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
        try:
            student_id, session_data = await get_session_data()
            print(f"[{datetime.now()}] ✅ Retrieved session data for student ID: {student_id}")
            case_id = session_data["case_id"]
            print(f"[{datetime.now()}] ✅ Working with case ID: {case_id}")
        except Exception as session_error:
            print(f"[{datetime.now()}] ❌ Error retrieving session data: {str(session_error)}")
            print(f"[{datetime.now()}] ❌ Error details: {type(session_error).__name__}")
            raise
        
        # Get analysis results from session
        try:
            if "feedback" not in session_data["interactions"]:
                print(f"[{datetime.now()}] ⚠️ 'feedback' key not found in session_data['interactions']")
                print(f"[{datetime.now()}] ⚠️ Available keys: {list(session_data['interactions'].keys())}")
                raise HTTPException(
                    status_code=400,
                    detail="Analysis results not found in session. Please run the analysis step first."
                )
            
            if "history_taking" not in session_data["interactions"]["feedback"]:
                print(f"[{datetime.now()}] ⚠️ 'history_taking' key not found in session_data['interactions']['feedback']")
                print(f"[{datetime.now()}] ⚠️ Available keys: {list(session_data['interactions']['feedback'].keys())}")
                raise HTTPException(
                    status_code=400,
                    detail="Analysis results not found in session. Please run the analysis step first."
                )
                
            if "analysis" not in session_data["interactions"]["feedback"]["history_taking"]:
                print(f"[{datetime.now()}] ⚠️ 'analysis' key not found in session_data['interactions']['feedback']['history_taking']")
                print(f"[{datetime.now()}] ⚠️ Available keys: {list(session_data['interactions']['feedback']['history_taking'].keys())}")
                raise HTTPException(
                    status_code=400,
                    detail="Analysis results not found in session. Please run the analysis step first."
                )
                
            analysis_result = session_data["interactions"]["feedback"]["history_taking"]["analysis"]
            print(f"[{datetime.now()}] ✅ Successfully retrieved analysis results from session")
        except KeyError as key_error:
            print(f"[{datetime.now()}] ❌ KeyError accessing session data: {str(key_error)}")
            print(f"[{datetime.now()}] ❌ Session data structure: {json.dumps(session_data, indent=2)[:500]}...")
            raise HTTPException(
                status_code=400,
                detail=f"Missing key in session data: {str(key_error)}"
            )
       
        # Load required data
        try:
            context = await load_case_context(int(case_id))
            print(f"[{datetime.now()}] ✅ Loaded case context, length: {len(context)} characters")
            expected_questions = await load_expected_questions(int(case_id))
            print(f"[{datetime.now()}] ✅ Loaded {len(expected_questions)} expected questions")
        except Exception as load_error:
            print(f"[{datetime.now()}] ❌ Error loading case data: {str(load_error)}")
            print(f"[{datetime.now()}] ❌ Error details: {type(load_error).__name__}")
            raise
        
        # Get student questions
        try:
            student_questions = [
                {
                    "question": interaction["question"],
                    "response": interaction["response"]
                }
                for interaction in session_data["interactions"]["history_taking"]
            ]
            print(f"[{datetime.now()}] ✅ Extracted {len(student_questions)} student questions")
        except Exception as extract_error:
            print(f"[{datetime.now()}] ❌ Error extracting student questions: {str(extract_error)}")
            print(f"[{datetime.now()}] ❌ Error details: {type(extract_error).__name__}")
            if "interactions" in session_data and "history_taking" in session_data["interactions"]:
                print(f"[{datetime.now()}] ❌ First history_taking item: {json.dumps(session_data['interactions']['history_taking'][0] if session_data['interactions']['history_taking'] else 'empty', indent=2)}")
            raise
        
        # Configure the model
        try:
            model = genai.GenerativeModel('gemini-2.0-flash')
            generation_config = {
                "temperature": 0.7,
                "top_p": 0.8,
                "top_k": 40
            }
            print(f"[{datetime.now()}] ✅ Configured Gemini model: {model.model_name}")
        except Exception as model_error:
            print(f"[{datetime.now()}] ❌ Error configuring Gemini model: {str(model_error)}")
            print(f"[{datetime.now()}] ❌ Error details: {type(model_error).__name__}")
            raise
        
        # Format the prompt with the required data
        try:
            formatted_prompt = HISTORY_AETCOM_PROMPT.format(
                case_context=context,
                expected_questions=json.dumps(expected_questions, indent=2),
                student_questions=json.dumps(student_questions, indent=2),
            )
            print(f"[{datetime.now()}] ✅ Formatted prompt, length: {len(formatted_prompt)} characters")
        except Exception as prompt_error:
            print(f"[{datetime.now()}] ❌ Error formatting prompt: {str(prompt_error)}")
            print(f"[{datetime.now()}] ❌ Error details: {type(prompt_error).__name__}")
            raise
        
        # Generate the feedback
        try:
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
            
            print(f"[{datetime.now()}] 🔄 Sending request to Gemini API...")
            response = await asyncio.to_thread(model.generate_content, **content)
            print(f"[{datetime.now()}] ✅ Received response from Gemini API, length: {len(response.text)} characters")
        except Exception as api_error:
            print(f"[{datetime.now()}] ❌ Error calling Gemini API: {str(api_error)}")
            print(f"[{datetime.now()}] ❌ Error details: {type(api_error).__name__}")
            raise
        
        # Process and return the response
        try:
            cleaned_content = clean_code_block(response.text)
            print(f"[{datetime.now()}] ✅ Cleaned response content, length: {len(cleaned_content)} characters")
            feedback_result = json.loads(cleaned_content)
            print(f"[{datetime.now()}] ✅ Parsed JSON response successfully")
        except json.JSONDecodeError as json_error:
            print(f"[{datetime.now()}] ❌ JSON parsing error: {str(json_error)}")
            print(f"[{datetime.now()}] ❌ First 500 chars of cleaned content: {cleaned_content[:500]}")
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to parse Gemini response as JSON: {str(json_error)}"
            )
        except Exception as parse_error:
            print(f"[{datetime.now()}] ❌ Error processing response: {str(parse_error)}")
            print(f"[{datetime.now()}] ❌ Error details: {type(parse_error).__name__}")
            raise
        
        # Save both analysis and domain feedback to session
        try:
            session_manager.add_history_feedback(
                student_id=student_id,
                analysis_result=analysis_result,
                domain_feedback=feedback_result
            )
            print(f"[{datetime.now()}] ✅ Successfully saved feedback results to session")
        except Exception as save_error:
            print(f"[{datetime.now()}] ⚠️ Failed to save feedback to session: {str(save_error)}")
            print(f"[{datetime.now()}] ⚠️ Error details: {type(save_error).__name__}")
        
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
        print(f"[{datetime.now()}] ❌ Error type: {type(e).__name__}")
        print(f"[{datetime.now()}] ❌ Error details: {str(e)}")
        import traceback
        print(f"[{datetime.now()}] ❌ Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=error_msg)

@router.post("/evaluate")
async def evaluate_history(
    history_data: dict,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Evaluate student history taking and provide feedback.
    """
    print(f"[HISTORY_FEEDBACK] 📝 Processing history evaluation request")
    
    # Extract token and authenticate the user
    try:
        token = credentials.credentials  # This is the raw JWT
        print(f"[DEBUG] Extracted JWT: {token}")
        
        print(f"[HISTORY_FEEDBACK] 🔐 Authenticating user...")
        user_response = await get_user_from_token(token)
        if not user_response["success"]:
            error_message = user_response.get("error", "Authentication required")
            print(f"[HISTORY_FEEDBACK] ❌ Authentication failed: {error_message}")
            raise HTTPException(status_code=401, detail=error_message)
        
        user_id = user_response["user"]["id"]
        print(f"[HISTORY_FEEDBACK] ✅ User authenticated successfully. User ID: {user_id}")
        
        try:
            # Your existing history evaluation logic here
            # ... existing code ...
            return {"message": "History evaluation completed successfully"}
        except Exception as e:
            print(f"[HISTORY_FEEDBACK] ❌ Error in history evaluation: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error in history evaluation: {str(e)}")
            
    except HTTPException as auth_error:
        print(f"[HISTORY_FEEDBACK] ❌ HTTP exception during authentication: {str(auth_error)}")
        raise auth_error
    except Exception as auth_error:
        print(f"[HISTORY_FEEDBACK] ❌ Unexpected error during authentication: {str(auth_error)}")
        raise HTTPException(status_code=401, detail="Authentication failed")
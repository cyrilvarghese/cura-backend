from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException, Body, Query, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from datetime import datetime
import os
from dotenv import load_dotenv
import json
from pathlib import Path
import google.generativeai as genai
from utils.text_cleaner import clean_code_block
from auth.auth_api import get_user_from_token
from utils.session_manager import SessionManager
import asyncio
from collections import Counter
from pydantic import BaseModel

# Load environment variables
load_dotenv()

# Define the security scheme
security = HTTPBearer()

# Constants
CASE_DATA_PATH_PATTERN = "case-data/case{}"
HISTORY_CONTEXT_FILENAME = "history_context.json"

router = APIRouter(
    prefix="/history-match",
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

# Load the prompt from file
HISTORY_MATCH_PROMPT = load_prompt("prompts/history_match.txt")

# Load the QA prompt from file
HISTORY_MATCH_QA_PROMPT = load_prompt("prompts/history_qanda.txt")

async def load_expected_questions(case_id: int) -> List[Dict[str, str]]:
    """Load the expected questions with domains from the history context file."""
    try:
        file_path = Path(f"{CASE_DATA_PATH_PATTERN.format(case_id)}/{HISTORY_CONTEXT_FILENAME}")
        if not file_path.exists():
            raise FileNotFoundError(f"History context not found for case {case_id}")
        
        with open(file_path, 'r') as file:
            data = json.load(file)
            # Extract the expected_questions_with_domains array from the JSON
            if "expected_questions_with_domains" in data:
                return data["expected_questions_with_domains"]
            else:
                raise ValueError("No 'expected_questions_with_domains' field found in history context file")
    except Exception as e:
        raise HTTPException(
            status_code=404,
            detail=f"Failed to load expected questions for case {case_id}: {str(e)}"
        )

class UnmatchedQuestionsRequest(BaseModel):
    remaining_unmatched_questions: List[Dict[str, str]] = []

class SingleInteractionRequest(BaseModel):
    current_interaction: Dict[str, str]
    uncovered_questions: List[Dict[str, str]] = []

@router.post("/unmatched-questions")
async def get_unmatched_questions(
    request: UnmatchedQuestionsRequest = Body(...),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Get a list of expected questions that were not asked by the student in their history taking.
    
    This endpoint:
    1. Gets student ID from authentication
    2. Gets case ID from the current session
    3. Extracts student interactions from the session
    4. Uses AI to compare against expected questions (either provided or loaded from file)
    5. Returns unmatched questions with their domains
    
    Request body (optional):
    - remaining_unmatched_questions: A list of previously unmatched questions with domains
      to check against instead of loading all expected questions from file
    
    Example request body:
    ```json
    {
        "remaining_unmatched_questions": [
            {
                "question": "Do you have any allergies to medications?",
                "domain": "Past Medical History"
            },
            {
                "question": "Do you smoke or drink alcohol?",
                "domain": "Social History"
            }
        ]
    }
    ```
    
    Example response:
    ```json
    {
        "case_id": "1",
        "student_id": "fa19f495-35e7-48cf-87c0-eabd94c7a05f",
        "timestamp": "2023-08-10T14:30:45.123456",
        "unmatched_questions": [
            {
                "question": "Do you have any allergies to medications?",
                "domain": "Past Medical History"
            }
        ],
        "domain_stats": {
            "Past Medical History": {
                "total": 5,
                "remaining": 1,
                "completed": 4,
                "percent_complete": 80
            },
            "Social History": {
                "total": 3,
                "remaining": 0,
                "completed": 3,
                "percent_complete": 100
            },
            "Overall": {
                "total": 8,
                "remaining": 1,
                "completed": 7,
                "percent_complete": 87.5
            }
        },
        "metadata": {
            "total_expected_questions": 8,
            "total_student_questions": 10,
            "total_unmatched_questions": 1,
            "processing_time_seconds": 2.5,
            "model_version": "gemini-2.0-flash"
        }
    }
    ```
    """
    print(f"[HISTORY_MATCH] 📋 Processing unmatched questions request")
    
    # Extract token and authenticate the user
    try:
        token = credentials.credentials  # This is the raw JWT
        print(f"[DEBUG] Extracted JWT: {token}")
        
        print(f"[HISTORY_MATCH] 🔐 Authenticating user...")
        user_response = await get_user_from_token(token)
        if not user_response["success"]:
            error_message = user_response.get("error", "Authentication required")
            print(f"[HISTORY_MATCH] ❌ Authentication failed: {error_message}")
            raise HTTPException(status_code=401, detail=error_message)
        
        student_id = user_response["user"]["id"]
        print(f"[HISTORY_MATCH] ✅ User authenticated successfully. Student ID: {student_id}")
        
        # Get session data and case ID
        session_data = session_manager.get_session(student_id)
        if not session_data:
            raise HTTPException(status_code=404, detail="No active session found")
        
        case_id = session_data["case_id"]
        
        # Load ALL expected questions for the case (for total counts)
        all_expected_questions = await load_expected_questions(int(case_id))
        
        # Extract the list from the request model
        remaining_unmatched_questions = request.remaining_unmatched_questions
        
        # Use remaining unmatched questions if provided (non-empty), otherwise use all expected questions
        if len(remaining_unmatched_questions) > 0:
            expected_questions_with_domains = remaining_unmatched_questions
            print(f"[{datetime.now()}] 📝 Using {len(remaining_unmatched_questions)} remaining questions from API parameter")
        else:
            # Use all expected questions as the current unmatched set
            expected_questions_with_domains = all_expected_questions
            print(f"[{datetime.now()}] 📝 Loaded {len(expected_questions_with_domains)} questions from case file")
        
        # Calculate domain totals
        total_by_domain = Counter()
        for question in expected_questions_with_domains:
            domain = question.get("domain", "Unknown")
            total_by_domain[domain] += 1
        
        # Create domain statistics for the empty case
        domain_stats = {}
        for domain in total_by_domain:
            total = total_by_domain[domain]
            domain_stats[domain] = {
                "total": total,
                "remaining": total,
                "completed": 0,
                "percent_complete": 0
            }
        
        # Add overall statistics
        overall_total = len(expected_questions_with_domains)
        domain_stats["Overall"] = {
            "total": overall_total,
            "remaining": overall_total,
            "completed": 0,
            "percent_complete": 0
        }
        
        # Extract interactions from session data (including both questions and responses)
        student_interactions = [
            {
                "student_question": interaction["question"],
                "patient_reply": interaction["response"]
            }
            for interaction in session_data["interactions"]["history_taking"]
        ]
        
        if not student_interactions:
            return {
                "case_id": case_id,
                "student_id": student_id,
                "timestamp": datetime.now().isoformat(),
                "unmatched_questions": expected_questions_with_domains,  # Return all questions as unmatched
                "domain_stats": domain_stats,  # Return domain stats with 0% completion
                "metadata": {
                    "total_expected_questions": len(expected_questions_with_domains),
                    "total_student_questions": 0,
                    "total_unmatched_questions": len(expected_questions_with_domains),
                    "error": "No interactions found in session"
                }
            }
        
        # Keep only these three print statements
        print(f"[{datetime.now()}] 📋 Expected Questions:\n{json.dumps(expected_questions_with_domains, indent=2)}")
        print(f"[{datetime.now()}] 🧑‍🎓 Student Interactions:\n{json.dumps(student_interactions, indent=2)}")
        
        # Configure the model
        model = genai.GenerativeModel('gemini-2.0-flash')
        generation_config = {
            "temperature": 0.3,
            "top_p": 0.95,
            "top_k": 40
        }
        
        # Format the prompt with the required data
        formatted_prompt = HISTORY_MATCH_PROMPT.format(
            expected_questions_with_domains=json.dumps(expected_questions_with_domains, indent=2),
            student_interactions=json.dumps(student_interactions, indent=2)
        )
        
        # Generate the response
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
        
        # Parse the JSON response
        try:
            unmatched_questions = json.loads(cleaned_content)
            # Keep this print statement for output
            print(f"[{datetime.now()}] 📊 Unmatched Questions Result:\n{json.dumps(unmatched_questions, indent=2)}")
        except json.JSONDecodeError as json_error:
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to parse Gemini response as JSON: {str(json_error)}"
            )
        
        # Calculate domain statistics
        # 1. Count total questions per domain from ALL questions
        total_by_domain = Counter()
        for question in all_expected_questions:
            domain = question.get("domain", "Unknown")
            total_by_domain[domain] += 1
        
        # 2. Count remaining questions per domain
        remaining_by_domain = Counter()
        for question in unmatched_questions:
            domain = question.get("domain", "Unknown")
            remaining_by_domain[domain] += 1
        
        # 3. Create domain statistics with percentages
        domain_stats = {}
        overall_total = len(all_expected_questions)
        overall_remaining = len(unmatched_questions)
        overall_completed = overall_total - overall_remaining
        
        for domain in total_by_domain:
            total = total_by_domain[domain]
            remaining = remaining_by_domain.get(domain, 0)
            completed = total - remaining
            percent_complete = int(round((completed / total) * 100)) if total > 0 else 0
            
            domain_stats[domain] = {
                "total": total,
                "remaining": remaining,
                "completed": completed,
                "percent_complete": percent_complete
            }
        
        # Add overall statistics
        domain_stats["Overall"] = {
            "total": overall_total,
            "remaining": overall_remaining,
            "completed": overall_completed,
            "percent_complete": int(round((overall_completed / overall_total) * 100)) if overall_total > 0 else 0
        }
        
        return {
            "case_id": case_id,
            "student_id": student_id,
            "timestamp": datetime.now().isoformat(),
            "unmatched_questions": unmatched_questions,
            "all_questions": all_expected_questions,
            "domain_stats": domain_stats,
            "metadata": {
                "total_expected_questions": overall_total,
                "total_student_questions": len(student_interactions),
                "total_unmatched_questions": len(unmatched_questions),
                "processing_time_seconds": (datetime.now() - start_time).total_seconds(),
                "model_version": model.model_name
            }
        }
        
    except HTTPException as auth_error:
        print(f"[HISTORY_MATCH] ❌ HTTP exception during authentication: {str(auth_error)}")
        raise auth_error
    except Exception as auth_error:
        print(f"[HISTORY_MATCH] ❌ Unexpected error during authentication: {str(auth_error)}")
        raise HTTPException(status_code=401, detail="Authentication failed")

@router.post("/match-single-interaction")
async def match_single_interaction(
    request: SingleInteractionRequest = Body(...),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Determine which outstanding questions are covered by a single student-patient interaction.
    
    This endpoint:
    1. Takes a single student-patient interaction (question and answer)
    2. Takes a list of currently uncovered expected questions
    3. Returns which of those questions are now considered covered by this interaction
    
    Request body:
    - current_interaction: Object with student_question and patient_reply fields
    - uncovered_questions: List of previously unmatched questions with domains
    
    Example request body:
    ```json
    {
        "current_interaction": {
            "student_question": "Do you have any allergies?",
            "patient_reply": "Yes, I'm allergic to penicillin and shellfish."
        },
        "uncovered_questions": [
            {
                "question": "Do you have any allergies to medications?",
                "domain": "Past Medical History"
            },
            {
                "question": "Do you have any food allergies?",
                "domain": "Past Medical History"
            }
        ]
    }
    ```
    
    Example response:
    ```json
    {
        "case_id": "1",
        "student_id": "fa19f495-35e7-48cf-87c0-eabd94c7a05f",
        "timestamp": "2023-08-10T14:30:45.123456",
        "covered_questions": [
            {
                "question": "Do you have any allergies to medications?",
                "domain": "Past Medical History"
            },
            {
                "question": "Do you have any food allergies?",
                "domain": "Past Medical History"
            }
        ],
        "unmatched_questions": [
            {
                "question": "Do you have any allergies to medications?",
                "domain": "Past Medical History"
            },
            {
                "question": "Do you have any food allergies?",
                "domain": "Past Medical History"
            }
        ],
        "domain_stats": {
            "Past Medical History": {
                "total": 2,
                "remaining": 0,
                "completed": 2,
                "percent_complete": 100
            },
            "Social History": {
                "total": 0,
                "remaining": 0,
                "completed": 0,
                "percent_complete": 0
            },
            "Overall": {
                "total": 2,
                "remaining": 0,
                "completed": 2,
                "percent_complete": 100
            }
        },
        "metadata": {
            "total_expected_questions": 2,
            "total_newly_covered_questions": 2,
            "total_remaining_questions": 0,
            "processing_time_seconds": 0.5,
            "model_version": "gemini-2.0-flash"
        }
    }
    ```
    """
    print(f"[HISTORY_MATCH] 🔍 Processing single interaction match request")
    
    # Extract token and authenticate the user
    try:
        token = credentials.credentials  # This is the raw JWT
        print(f"[DEBUG] Extracted JWT: {token}")
        
        print(f"[HISTORY_MATCH] 🔐 Authenticating user...")
        user_response = await get_user_from_token(token)
        if not user_response["success"]:
            error_message = user_response.get("error", "Authentication required")
            print(f"[HISTORY_MATCH] ❌ Authentication failed: {error_message}")
            raise HTTPException(status_code=401, detail=error_message)
        
        student_id = user_response["user"]["id"]
        print(f"[HISTORY_MATCH] ✅ User authenticated successfully. Student ID: {student_id}")
        
        # Validate input
        current_interaction = request.current_interaction
        uncovered_questions = request.uncovered_questions
        
        # Ensure the current_interaction has the right fields
        if "student_question" not in current_interaction or "patient_reply" not in current_interaction:
            raise HTTPException(
                status_code=400, 
                detail="current_interaction must include student_question and patient_reply fields"
            )
            
        # Get session data and case ID
        session_data = session_manager.get_session(student_id)
        if not session_data:
            raise HTTPException(status_code=404, detail="No active session found")
        
        case_id = session_data["case_id"]
        
        # Get all questions from the case
        all_questions = await load_expected_questions(int(case_id))
        
        # If there are no uncovered questions, use all questions
        if not uncovered_questions:
            uncovered_questions = all_questions
            print(f"[{datetime.now()}] 📝 No questions provided, loaded {len(uncovered_questions)} questions from case file")
        
        # Log the inputs
        print(f"[{datetime.now()}] 🧑‍🎓 Current Interaction:\n{json.dumps(current_interaction, indent=2)}")
        print(f"[{datetime.now()}] 📋 Uncovered Questions:\n{json.dumps(uncovered_questions, indent=2)}")
        
        # Configure the model
        model = genai.GenerativeModel('gemini-2.0-flash')
        generation_config = {
            "temperature": 0.3,
            "top_p": 0.95,
            "top_k": 40
        }
        
        # Format the prompt with the required data
        formatted_prompt = HISTORY_MATCH_QA_PROMPT.format(
            student_interactions=json.dumps(current_interaction, indent=2),
            uncovered_expected_questions=json.dumps(uncovered_questions, indent=2)
        )
        
        # Generate the response
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
        
        # Parse the JSON response
        try:
            covered_questions = json.loads(cleaned_content)
            print(f"[{datetime.now()}] 📊 Covered Questions Result:\n{json.dumps(covered_questions, indent=2)}")
        except json.JSONDecodeError as json_error:
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to parse Gemini response as JSON: {str(json_error)}"
            )
        
        # Calculate remaining unmatched questions (those not covered by this interaction)
        covered_question_texts = [(q["question"], q["domain"]) for q in covered_questions]
        remaining_unmatched = []
        for q in uncovered_questions:
            if (q["question"], q["domain"]) not in covered_question_texts:
                remaining_unmatched.append(q)
        
        # Calculate domain statistics
        # 1. Count total questions per domain from ALL questions
        total_by_domain = Counter()
        for question in all_questions:
            domain = question.get("domain", "Unknown")
            total_by_domain[domain] += 1
        
        # 2. Count remaining questions per domain
        remaining_by_domain = Counter()
        for question in remaining_unmatched:
            domain = question.get("domain", "Unknown")
            remaining_by_domain[domain] += 1
        
        # 3. Create domain statistics with percentages
        domain_stats = {}
        for domain in total_by_domain:
            total = total_by_domain[domain]
            
            # For this domain, count how many questions were in the uncovered list
            domain_uncovered = sum(1 for q in uncovered_questions if q.get("domain") == domain)
            
            # For this domain, count how many questions remain uncovered after this interaction
            domain_remaining = remaining_by_domain.get(domain, 0)
            
            # Calculate how many questions were covered in this domain by this interaction
            newly_covered = sum(1 for q in covered_questions if q.get("domain") == domain)
            
            # Calculate how many questions are completed overall for this domain
            # This means: total questions - remaining after this interaction
            completed = total - domain_remaining
            
            percent_complete = int(round((completed / total) * 100)) if total > 0 else 0
            
            domain_stats[domain] = {
                "total": total,
                "remaining": domain_remaining,
                "completed": completed,
                "percent_complete": percent_complete
            }
        
        # Add overall statistics
        overall_total = len(all_questions)
        overall_remaining = len(remaining_unmatched)
        overall_completed = overall_total - overall_remaining
        
        domain_stats["Overall"] = {
            "total": overall_total,
            "remaining": overall_remaining,
            "completed": overall_completed,
            "percent_complete": int(round((overall_completed / overall_total) * 100)) if overall_total > 0 else 0
        }
        
        return {
            "case_id": case_id,
            "student_id": student_id,
            "timestamp": datetime.now().isoformat(),
            "covered_questions": covered_questions,
            "unmatched_questions": remaining_unmatched,
            "all_questions": all_questions,
            "domain_stats": domain_stats,
            "metadata": {
                "total_expected_questions": len(uncovered_questions),
                "total_newly_covered_questions": len(covered_questions),
                "total_remaining_questions": len(remaining_unmatched),
                "processing_time_seconds": (datetime.now() - start_time).total_seconds(),
                "model_version": model.model_name
            }
        }
        
    except HTTPException as auth_error:
        print(f"[HISTORY_MATCH] ❌ HTTP exception during authentication: {str(auth_error)}")
        raise auth_error
    except Exception as auth_error:
        print(f"[HISTORY_MATCH] ❌ Unexpected error during authentication: {str(auth_error)}")
        raise HTTPException(status_code=401, detail="Authentication failed") 
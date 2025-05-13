from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException, Body, Query
from datetime import datetime
import os
from dotenv import load_dotenv
import json
from pathlib import Path
import google.generativeai as genai
from utils.text_cleaner import clean_code_block
from auth.auth_api import get_user
from utils.session_manager import SessionManager
import asyncio
from collections import Counter

# Load environment variables
load_dotenv()

# Constants
CASE_DATA_PATH_PATTERN = "case-data/case{}"
HISTORY_CONTEXT_FILENAME = "history_context.json"

router = APIRouter(
    prefix="/history-match",
    tags=["history-match"]
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

@router.get("/unmatched-questions")
async def get_unmatched_questions():
    """
    Get a list of expected questions that were not asked by the student in their history taking.
    
    This endpoint:
    1. Gets student ID from authentication
    2. Gets case ID from the current session
    3. Extracts student questions from the session
    4. Uses AI to compare against expected questions
    5. Returns unmatched questions with their domains
    
    No request body or path parameters needed - everything is derived from the authenticated session.
    
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
            },
            {
                "question": "Do you smoke or drink alcohol?",
                "domain": "Social History"
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
                "remaining": 1,
                "completed": 2,
                "percent_complete": 67
            },
            "Overall": {
                "total": 10,
                "remaining": 2,
                "completed": 8,
                "percent_complete": 80
            }
        },
        "metadata": {
            "total_expected_questions": 10,
            "total_student_questions": 8,
            "total_unmatched_questions": 2,
            "processing_time_seconds": 2.5,
            "model_version": "gemini-2.0-flash"
        }
    }
    ```
    """
    try:
        # Get student ID from authentication
        user_response = await get_user()
        if not user_response["success"]:
            raise HTTPException(status_code=401, detail="Authentication required")
        
        student_id = user_response["user"]["id"]
        
        # Get session data and case ID
        session_data = session_manager.get_session(student_id)
        if not session_data:
            raise HTTPException(status_code=404, detail="No active session found")
        
        case_id = session_data["case_id"]
        
        # Load expected questions with domains first, so we have them even if no student questions
        expected_questions_with_domains = await load_expected_questions(int(case_id))
        
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
        # 2. Count remaining questions per domain
        remaining_by_domain = Counter()
        for question in unmatched_questions:
            domain = question.get("domain", "Unknown")
            remaining_by_domain[domain] += 1
        
        # 3. Create domain statistics with percentages
        domain_stats = {}
        overall_total = len(expected_questions_with_domains)
        overall_remaining = len(unmatched_questions)
        overall_completed = overall_total - overall_remaining
        
        for domain in total_by_domain:
            total = total_by_domain[domain]
            remaining = remaining_by_domain[domain]
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
            "domain_stats": domain_stats,
            "metadata": {
                "total_expected_questions": len(expected_questions_with_domains),
                "total_student_questions": len(student_interactions),
                "total_unmatched_questions": len(unmatched_questions),
                "processing_time_seconds": (datetime.now() - start_time).total_seconds(),
                "model_version": model.model_name
            }
        }
        
    except Exception as e:
        error_msg = f"Error in get_unmatched_questions: {str(e)}"
        import traceback
        raise HTTPException(status_code=500, detail=error_msg) 
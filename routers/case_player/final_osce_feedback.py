from typing import Dict, Optional
from fastapi import APIRouter, HTTPException
from datetime import datetime
import os
from dotenv import load_dotenv
import json
from pathlib import Path
from pydantic import BaseModel
import google.generativeai as genai
from utils.text_cleaner import clean_code_block
import asyncio

# Load environment variables
load_dotenv()

router = APIRouter(
    prefix="/final-osce-feedback",
    tags=["create-osce-feedback"]
)

class ConceptModal(BaseModel):
    specific: str
    general: str
    lateral: str

class Options(BaseModel):
    A: str
    B: str
    C: str
    D: str

class Question(BaseModel):
    station_title: str
    question_format: str
    addressed_gap: str
    prompt: str
    options: Optional[Options] = None  # <-- fix here
    mcq_correct_answer_key: Optional[str] = None  # <-- fix here
    expected_answer: Optional[str] = None
    explanation: str
    concept_modal: ConceptModal

class StudentResponse(BaseModel):
    student_mcq_choice_key: Optional[str] = None  # <-- fix here
    student_written_answer: Optional[str] = None

class OSCEFeedbackRequest(BaseModel):
    case_id: str
    question: Question
    student_response: StudentResponse

    class Config:
        json_schema_extra = {
            "example": {
                "case_id": "1",
                "question": {
                    "station_title": "Differentiating Based on Lesion Duration",
                    "question_format": "MCQ",
                    "addressed_gap": "Gap: Failure to use lesion duration as a key differentiator between urticarial vasculitis and chronic spontaneous urticaria.",
                    "prompt": "A patient presents with itchy, red welts...",
                    "options": {
                        "A": "Urticarial vasculitis",
                        "B": "Chronic spontaneous urticaria",
                        "C": "Erythema multiforme",
                        "D": "Fixed drug eruption"
                    },
                    "mcq_correct_answer_key": "B",
                    "expected_answer": None,
                    "explanation": "Lesions lasting <24 hours without residual changes...",
                    "concept_modal": {
                        "specific": "Lesion duration is a critical differentiating feature...",
                        "general": "Careful history taking regarding...",
                        "lateral": "Temporal patterns are key in differentiating..."
                    }
                },
                "student_response": {
                    "student_mcq_choice_key": "B",
                    "student_written_answer": None
                }
            }
        }

def load_prompt(file_path: str) -> str:
    """Load the prompt from a specified file."""
    try:
        with open(file_path, 'r') as file:
            return file.read()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Prompt file not found: {file_path}")

# Load the prompt from file
OSCE_FEEDBACK_PROMPT = load_prompt("prompts/OSCE_question_feedback.md")

@router.post("")
async def get_osce_feedback(request: OSCEFeedbackRequest):
    """Generate feedback for OSCE questions using Gemini."""
    try:
        print(f"\n[{datetime.now()}] 🔍 Starting OSCE feedback generation")
        print(f"[DEBUG] Request data: {request.model_dump_json(indent=2)}")
        
        start_time = datetime.now()
        
        # Configure the model
        model = genai.GenerativeModel('gemini-2.0-flash')
        generation_config = {
            "temperature": 0.7,
            "top_p": 0.8,
            "top_k": 40
        }
        print(f"[DEBUG] Model configuration: {generation_config}")
        
        # Format the prompt by replacing the placeholders
        formatted_prompt = OSCE_FEEDBACK_PROMPT.replace(
            "{osce_question_details_json}", 
            json.dumps(request.question.model_dump(), indent=2)
        ).replace(
            "{student_response_json}", 
            json.dumps(request.student_response.model_dump(), indent=2)
        )
        
        print(f"[DEBUG] Formatted prompt first 200 chars: {formatted_prompt[:200]}...")
        
        # Prepare the content for generation
        content = {
            "contents": [{"parts": [{"text": formatted_prompt}]}],
            "generation_config": generation_config
        }
        
        # Generate the response
        print("[DEBUG] Sending prompt to Gemini model...")
        response = await asyncio.to_thread(model.generate_content, **content)
        print("[DEBUG] Received response from Gemini model")
        
        # Process the response content
        response_content = response.text
        print(f"[DEBUG] Raw response content: {response_content}")
        
        # Clean the response and parse as JSON
        try:
            cleaned_content = clean_code_block(response_content)
            print(f"[DEBUG] Cleaned content: {cleaned_content}")
            feedback_result = json.loads(cleaned_content)
            print(f"[DEBUG] Parsed JSON result: {json.dumps(feedback_result, indent=2)}")
        except json.JSONDecodeError as je:
            print(f"[DEBUG] JSON parse error: {str(je)}")
            print(f"[DEBUG] Failed content: {cleaned_content}")
            feedback_result = {
                "evaluation_result": "Error",
                "score": 0,
                "feedback": f"Error parsing model response: {str(je)}",
                "grading_rationale": "Error occurred during feedback generation"
            }
        
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        
        response_data = {
            "case_id": request.case_id,
            "timestamp": datetime.now().isoformat(),
            "feedback": feedback_result,
            "metadata": {
                "processing_time_seconds": processing_time,
                "model_version": model.model_name,
                "generation_config": generation_config
            }
        }
        
        print(f"[{datetime.now()}] ✅ Successfully generated OSCE feedback")
        print(f"[DEBUG] Final response data: {json.dumps(response_data, indent=2)}")
        return response_data

    except json.JSONDecodeError as e:
        error_msg = f"[{datetime.now()}] ❌ JSON parsing error: {str(e)}\n"
        error_msg += f"[DEBUG] Failed JSON content: {response_content}\n"
        error_msg += f"[DEBUG] Exception details: {str(e)}"
        print(error_msg)
        raise HTTPException(status_code=400, detail=error_msg)
    except Exception as e:
        error_msg = f"[{datetime.now()}] ❌ Error in get_osce_feedback:\n"
        error_msg += f"[DEBUG] Error type: {type(e).__name__}\n"
        error_msg += f"[DEBUG] Error message: {str(e)}\n"
        error_msg += f"[DEBUG] Request data: {request.model_dump_json()}"
        print(error_msg)
        raise HTTPException(status_code=500, detail=error_msg) 
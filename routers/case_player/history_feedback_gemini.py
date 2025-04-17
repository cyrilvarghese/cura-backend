from typing import List
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
    prefix="/history-feedback",
    tags=["history-feedback"]
)

class HistoryFeedbackRequest(BaseModel):
    case_id: str
    student_questions: List[str]

    class Config:
        json_schema_extra = {
            "example": {
                "case_id": "16",
                "student_questions": [
                    "Are you experiencing any pain?",
                    "How long have you been sick?"
                ]
            }
        }

# Initialize Gemini client
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

async def load_case_context(case_id: int) -> str:
    """Load the history-taking context from the case file."""
    try:
        file_path = Path(f"case-data/case{case_id}/case_doc.txt")
        if not file_path.exists():
            raise FileNotFoundError(f"Context file not found for case {case_id}")
        
        with open(file_path, 'r') as file:
            return file.read()
    except Exception as e:
        raise HTTPException(
            status_code=404, 
            detail=f"Failed to load context for case {case_id}: {str(e)}"
        )

async def load_expected_questions(case_id: int) -> List[str]:
    """Load the expected history questions from the case file."""
    try:
        file_path = Path(f"case-data/case{case_id}/expected_history.json")
        if not file_path.exists():
            raise FileNotFoundError(f"Expected questions file not found for case {case_id}")
        
        with open(file_path, 'r') as file:
            return json.load(file)  # Direct array load
    except Exception as e:
        raise HTTPException(
            status_code=404, 
            detail=f"Failed to load expected questions for case {case_id}: {str(e)}"
        )

def load_prompt(file_path: str) -> str:
    """Load the prompt from a specified file."""
    try:
        with open(file_path, 'r') as file:
            return file.read()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Prompt file not found: {file_path}")

# Load the prompt
HISTORY_FEEDBACK_PROMPT = load_prompt("prompts/history_feedback.txt")

@router.post("/evaluate")
async def evaluate_history_taking(request: HistoryFeedbackRequest):
    """Generate feedback for history-taking performance using Gemini."""
    try:
        print(f"[{datetime.now()}] 🔍 Starting history-taking evaluation")
        print(f"[DEBUG] Request data: {request.model_dump_json(indent=2)}")
        
        # Load case context and expected questions
        context = await load_case_context(int(request.case_id))
        expected_questions = await load_expected_questions(int(request.case_id))
        
        start_time = datetime.now()
        
        # Configure the model
        model = genai.GenerativeModel('gemini-2.0-flash')
        generation_config = {
            "temperature": 0.7,
            "top_p": 0.8,
            "top_k": 40
        }
 
        # Format the prompt
        formatted_prompt = f"""
        {HISTORY_FEEDBACK_PROMPT}

        Case Context:
        {context}

        Expected Questions:
        {json.dumps(expected_questions, indent=2)}

        Student's Questions:
        {json.dumps(request.student_questions, indent=2)}
        """

        # Prepare the content for generation
        content = {
            "contents": [{"parts": [{"text": formatted_prompt}]}],
            "generation_config": generation_config
        }
        
        # Generate feedback
        print("[DEBUG] Sending prompt to Gemini model...")
        response = await asyncio.to_thread(model.generate_content, **content)
        print("[DEBUG] Received response from Gemini model")
        
        # Process response
        response_content = response.text
        cleaned_content = clean_code_block(response_content)
        feedback_result = json.loads(cleaned_content)
        
        # Calculate overall score
        question_scores = [q["score"] for q in feedback_result["question_analysis"]]
        overall_score = sum(question_scores) / len(question_scores) if question_scores else 0
        
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        
        response_data = {
            "case_id": request.case_id,
            "timestamp": datetime.now().isoformat(),
            "feedback": feedback_result,
            "overall_score": overall_score,
            "metadata": {
                "total_questions_evaluated": len(expected_questions),
                "processing_time_seconds": processing_time,
                "model_version": model.model_name,
                "generation_config": generation_config
            }
        }
        
        print(f"[{datetime.now()}] ✅ Successfully generated history-taking feedback")
        return response_data

    except json.JSONDecodeError as e:
        error_msg = f"JSON parsing error: {str(e)}"
        print(f"[{datetime.now()}] ❌ {error_msg}")
        raise HTTPException(status_code=400, detail=error_msg)
    except Exception as e:
        error_msg = f"Error in evaluate_history_taking: {str(e)}"
        print(f"[{datetime.now()}] ❌ {error_msg}")
        raise HTTPException(status_code=500, detail=error_msg) 
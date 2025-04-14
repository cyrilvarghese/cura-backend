from typing import List
from fastapi import APIRouter, HTTPException
from datetime import datetime
import os
from dotenv import load_dotenv
import json
from pathlib import Path
from pydantic import BaseModel
import openai
from utils.text_cleaner import clean_code_block

# Load environment variables
load_dotenv()

router = APIRouter(
    prefix="/feedback",
    tags=["create-feedback"]
)

class PreTreatmentFeedbackRequest(BaseModel):
    case_id: str
    student_inputs_pre_treatment: List[str]
    student_inputs_monitoring: List[str]

# Initialize the OpenAI client
client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def load_prompt(file_path: str) -> str:
    """Load the prompt from a specified file."""
    try:
        with open(file_path, 'r') as file:
            return file.read()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Prompt file not found: {file_path}")

# Load the prompt from file
PRE_TREATMENT_FEEDBACK_PROMPT = load_prompt("prompts/pre_treatment_feedback.txt")
MONITORING_FEEDBACK_PROMPT = load_prompt("prompts/monitoring_feedback.txt")

async def load_case_context(case_id: int) -> str:
    """Load the pre-treatment context from the case file."""
    try:
        file_path = Path(f"case-data/case{case_id}/treatment_context.md")
        if not file_path.exists():
            raise FileNotFoundError(f"Context file not found for case {case_id}")
        
        with open(file_path, 'r') as file:
            return file.read()
    except Exception as e:
        raise HTTPException(
            status_code=404, 
            detail=f"Failed to load context for case {case_id}: {str(e)}"
        )

async def save_feedback_response(case_id: int, response_data: dict) -> dict:
    """Save the feedback response to a JSON file."""
    try:
        feedback_dir = Path(f"case-data/case{case_id}/feedback")
        feedback_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = feedback_dir / f"pre_treatment_feedback.json"
        
        with open(file_path, 'w') as f:
            json.dump(response_data, f, indent=4)
            
        return {
            "file_path": str(file_path),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save feedback: {str(e)}"
        )

@router.post("/pre_treatment_openai")
async def get_pre_treatment_feedback(request: PreTreatmentFeedbackRequest):
    """Generate feedback for pre-treatment test selections using OpenAI API directly."""
    try:
        print(f"[{datetime.now()}] Starting feedback generation for case: {request.case_id}")
        
        case_context = await load_case_context(request.case_id)
        
        feedback_results = {}
        start_time = datetime.now()
        
        for test in request.student_inputs_pre_treatment:
            print(f"[{datetime.now()}] Generating feedback for test: {test}")
            
            # Create the message with the prompt template
            messages = [
                {"role": "system", "content": "You are a helpful medical education assistant."},
                {"role": "user", "content": PRE_TREATMENT_FEEDBACK_PROMPT.format(
                    student_input_pre_treatment=test,
                    case_context=case_context
                )}
            ]
            
            # Call the OpenAI API directly
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                temperature=0.7
            )
            
            # Process the response content
            response_content = response.choices[0].message.content
            
            # Clean the response and parse as JSON
            try:
                cleaned_content = clean_code_block(response_content)
                feedback_results[test] = json.loads(cleaned_content)
            except json.JSONDecodeError:
                # If parsing fails, return a default response
                feedback_results[test] = {
                    "match": "NA",
                    "specific": "Error parsing response",
                    "general": "",
                    "lateral": ""
                }
        
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        
        response_data = {
            "case_id": request.case_id,
            "timestamp": datetime.now().isoformat(),
            "feedback": feedback_results,
            "metadata": {
                "total_tests_evaluated_pre_treatment": len(request.student_inputs_pre_treatment),
                "total_tests_evaluated_monitoring": len(request.student_inputs_monitoring),
                "processing_time_seconds": processing_time,
                "model_version": "gpt-4o"
            }
        }
        
        save_result = await save_feedback_response(request.case_id, response_data)
        response_data["file_path"] = save_result["file_path"]
        
        print(f"[{datetime.now()}] ✅ Successfully generated feedback")
        return response_data

    except json.JSONDecodeError as e:
        print(f"[{datetime.now()}] ❌ JSON parsing error: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Invalid response format: {str(e)}")
    except Exception as e:
        error_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{error_timestamp}] ❌ Error in get_pre_treatment_feedback: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/monitoring_openai")
async def get_monitoring_feedback(request: PreTreatmentFeedbackRequest):
    """Generate feedback for monitoring test selections using OpenAI API directly."""
    try:
        print(f"[{datetime.now()}] Starting feedback generation for case: {request.case_id}")

        case_context = await load_case_context(request.case_id)
        
        feedback_results = {}
        start_time = datetime.now()
        
        for test in request.student_inputs_monitoring:
            print(f"[{datetime.now()}] Generating feedback for test: {test}")
            
            # Create the message with the prompt template
            messages = [
                {"role": "system", "content": "You are a helpful medical education assistant."},
                {"role": "user", "content": MONITORING_FEEDBACK_PROMPT.format(
                    student_input_monitoring=test,
                    monitoring_context=case_context
                )}
            ]
            
            # Call the OpenAI API directly
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                temperature=0.7
            )
            
            # Process the response content
            response_content = response.choices[0].message.content
            
            # Clean the response and parse as JSON
            try:
                cleaned_content = clean_code_block(response_content)
                feedback_results[test] = json.loads(cleaned_content)
            except json.JSONDecodeError:
                # If parsing fails, return a default response
                feedback_results[test] = {
                    "match": "NA",
                    "specific": "Error parsing response",
                    "general": "",
                    "lateral": ""
                }
        
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        
        response_data = {
            "case_id": request.case_id,
            "timestamp": datetime.now().isoformat(),
            "feedback": feedback_results,
            "metadata": {
                "total_tests_evaluated": len(request.student_inputs_monitoring),
                "processing_time_seconds": processing_time,
                "model_version": "gpt-4o"
            }
        }
        
        save_result = await save_feedback_response(request.case_id, response_data)
        response_data["file_path"] = save_result["file_path"]
        
        print(f"[{datetime.now()}] ✅ Successfully generated monitoring feedback")
        return response_data

    except json.JSONDecodeError as e:
        print(f"[{datetime.now()}] ❌ JSON parsing error: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Invalid response format: {str(e)}")
    except Exception as e:
        error_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{error_timestamp}] ❌ Error in get_monitoring_feedback: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) 
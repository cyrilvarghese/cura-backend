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
    prefix="/feedback",
    tags=["create-feedback"]
)

class PreTreatmentFeedbackRequest(BaseModel):
    case_id: str
    student_inputs_pre_treatment: List[str] | None = None
    student_inputs_monitoring: List[str] | None = None
    student_input_pre_treatment: List[str] | None = None  # Backward compatibility
    student_input_monitoring: List[str] | None = None     # Backward compatibility

    def get_pre_treatment_inputs(self) -> List[str]:
        """Get pre-treatment inputs from either field name."""
        return self.student_inputs_pre_treatment or self.student_input_pre_treatment or []

    def get_monitoring_inputs(self) -> List[str]:
        """Get monitoring inputs from either field name."""
        return self.student_inputs_monitoring or self.student_input_monitoring or []

    class Config:
        # Add schema extra to show example
        json_schema_extra = {
            "example": {
                "case_id": "16",
                "student_inputs_pre_treatment": ["test1", "test2"],
                "student_inputs_monitoring": ["monitor1", "monitor2"]
            }
        }

class TreatmentProtocolRequest(BaseModel):
    case_id: str
    drug_line: str
    student_reasoning: str | None = None
    first_line: bool = False

    class Config:
        json_schema_extra = {
            "example": {
                "case_id": "16",
                "drug_line": "amoxicillin 500mg PO TID",
                "student_reasoning": "First line treatment for bacterial infection",
                "first_line": True
            }
        }

# Initialize the Gemini client
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

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
TREATMENT_FEEDBACK_PROMPT = load_prompt("prompts/treatment_feedback.txt")

async def load_case_context(case_id: int) -> str:
    """Load the treatment context from the case file."""
    try:
        file_path = Path(f"case-data/case{case_id}/treatment_context.json")
        if not file_path.exists():
            raise FileNotFoundError(f"Context file not found for case {case_id}")
        
        with open(file_path, 'r') as file:
            # Load the JSON data
            context_data = json.load(file)
            # Return the JSON data as a string for the prompt
            return json.dumps(context_data, indent=2)
    except Exception as e:
        raise HTTPException(
            status_code=404, 
            detail=f"Failed to load context for case {case_id}: {str(e)}"
        )

async def save_feedback_response(case_id: str, response_data: dict) -> dict:
    """Save the feedback response to a file."""
    try:
        # Create directory if it doesn't exist
        output_dir = Path(f"case-data/case{case_id}/feedback")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate a filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = output_dir / f"pre_treatment_feedback_gemini_{timestamp}.json"
        
        # Save the response to the file
        with open(file_path, 'w') as f:
            json.dump(response_data, f, indent=2)
        
        return {"status": "success", "file_path": str(file_path)}
    except Exception as e:
        print(f"Error saving feedback response: {e}")
        return {"status": "error", "message": str(e)}

@router.post("/pre_treatment_gemini")
async def get_pre_treatment_feedback(request: PreTreatmentFeedbackRequest):
    """Generate feedback for pre-treatment tests using Gemini Flash Lite."""
    try:
        print("\n=== DEBUG REQUEST INFO ===")
        print(f"[DEBUG] Raw request model: {request}")
        print(f"[DEBUG] Request dict: {request.dict()}")
        print(f"[DEBUG] Request fields: {request.model_fields_set}")
        print(f"[DEBUG] Pre-treatment inputs: {request.get_pre_treatment_inputs()}")
        print("=== END DEBUG INFO ===\n")
        
        print(f"[{datetime.now()}] 🔍 Generating pre-treatment feedback for case {request.case_id}")
        
        # Load the case context
        print("[DEBUG] Attempting to load case context...")
        context = await load_case_context(int(request.case_id))
        print(f"[DEBUG] Successfully loaded context length: {len(context)}")
        
        start_time = datetime.now()
        feedback_results = {}
        
        # Configure the model with high temperature for more creative responses
        model = genai.GenerativeModel('gemini-2.0-flash')
        generation_config = {
            "temperature": 0.9,  # High temperature for more creative responses
            "top_p": 0.8,       # Slightly lower top_p to maintain some consistency
            "top_k": 40         # Reasonable top_k for diverse but relevant outputs
        }
        
        # Process each test input
        for test in request.get_pre_treatment_inputs():
            print(f"[{datetime.now()}] Evaluating test: {test}")
            
            # Prepare the prompt with the specific test
            content = {
                "contents": [
                    {
                        "parts": [
                            {"text": PRE_TREATMENT_FEEDBACK_PROMPT},
                            {"text": f"\nContext: {context}"},
                            {"text": f"\nTest: {test}"}
                        ]
                    }
                ],
                "generation_config": generation_config
            }
            
            # Generate the response
            print("[DEBUG] Sending prompt to Gemini model...")
            print(f"[DEBUG] Content structure: {json.dumps(content, indent=2)}")
            response = await asyncio.to_thread(model.generate_content, **content)
            print("[DEBUG] Received response from Gemini model")
            
            # Process the response content
            response_content = response.text
            print(f"[DEBUG] Raw response content: {response_content[:100]}...")
            
            # Clean the response and parse as JSON
            try:
                cleaned_content = clean_code_block(response_content)
                print(f"[DEBUG] Cleaned content: {cleaned_content[:100]}...")
                feedback_results[test] = json.loads(cleaned_content)
            except json.JSONDecodeError as je:
                print(f"[DEBUG] JSON parse error: {str(je)}")
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
                "total_tests_evaluated": len(request.get_pre_treatment_inputs()),
                "processing_time_seconds": processing_time,
                "model_version": model.model_name,
                "generation_config": generation_config  # Include config in metadata
            }
        }
        
        # save_result = await save_feedback_response(request.case_id, response_data)
        # response_data["file_path"] = save_result["file_path"]
        
        print(f"[{datetime.now()}] ✅ Successfully generated pre-treatment feedback")
        return response_data

    except json.JSONDecodeError as e:
        print(f"[{datetime.now()}] ❌ JSON parsing error: {str(e)}")
        print(f"[DEBUG] Failed JSON content: {response_content}")
        raise HTTPException(status_code=400, detail=f"Invalid response format: {str(e)}")
    except Exception as e:
        error_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{error_timestamp}] ❌ Error in get_pre_treatment_feedback: {str(e)}")
        print(f"[DEBUG] Error type: {type(e).__name__}")
        print(f"[DEBUG] Full error details: {str(e)}")
        print(f"[DEBUG] Request data at time of error: {request.dict()}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/monitoring_gemini")
async def get_monitoring_feedback(request: PreTreatmentFeedbackRequest):
    """Generate feedback for monitoring tests using Gemini Flash Lite."""
    try:
        print("\n=== DEBUG REQUEST INFO ===")
        print(f"[DEBUG] Raw request model: {request}")
        print(f"[DEBUG] Request dict: {request.dict()}")
        print(f"[DEBUG] Request fields: {request.model_fields_set}")
        print(f"[DEBUG] Monitoring inputs: {request.get_monitoring_inputs()}")
        print("=== END DEBUG INFO ===\n")
        
        print(f"[{datetime.now()}] 🔍 Generating monitoring feedback for case {request.case_id}")
        
        # Load the case context
        context = await load_case_context(int(request.case_id))
        
        start_time = datetime.now()
        feedback_results = {}
        
        # Configure the model with high temperature for more creative responses
        model = genai.GenerativeModel('gemini-2.0-flash-lite')
        generation_config = {
            "temperature": 0.9,  # High temperature for more creative responses
            "top_p": 0.8,       # Slightly lower top_p to maintain some consistency
            "top_k": 40         # Reasonable top_k for diverse but relevant outputs
        }
        
        # Process each test input
        for test in request.get_monitoring_inputs():
            print(f"[{datetime.now()}] Evaluating test: {test}")
            
            # Prepare the prompt with the specific test
            content = {
                "contents": [
                    {
                        "parts": [
                            {"text": MONITORING_FEEDBACK_PROMPT},
                            {"text": f"\nContext: {context}"},
                            {"text": f"\nTest: {test}"}
                        ]
                    }
                ],
                "generation_config": generation_config
            }
            
            # Generate the response
            print("[DEBUG] Sending prompt to Gemini model...")
            print(f"[DEBUG] Content structure: {json.dumps(content, indent=2)}")
            response = await asyncio.to_thread(model.generate_content, **content)
            print("[DEBUG] Received response from Gemini model")
            
            # Process the response content
            response_content = response.text
            print(f"[DEBUG] Raw response content: {response_content[:100]}...")
            
            # Clean the response and parse as JSON
            try:
                cleaned_content = clean_code_block(response_content)
                print(f"[DEBUG] Cleaned content: {cleaned_content[:100]}...")
                feedback_results[test] = json.loads(cleaned_content)
            except json.JSONDecodeError as je:
                print(f"[DEBUG] JSON parse error: {str(je)}")
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
                "total_tests_evaluated": len(request.get_monitoring_inputs()),
                "processing_time_seconds": processing_time,
                "model_version": "gemini-2.0-flash-lite",
                "generation_config": generation_config  # Include config in metadata
            }
        }
        
        # save_result = await save_feedback_response(request.case_id, response_data)
        # response_data["file_path"] = save_result["file_path"]
        
        print(f"[{datetime.now()}] ✅ Successfully generated monitoring feedback")
        return response_data

    except json.JSONDecodeError as e:
        print(f"[{datetime.now()}] ❌ JSON parsing error: {str(e)}")
        print(f"[DEBUG] Failed JSON content: {response_content}")
        raise HTTPException(status_code=400, detail=f"Invalid response format: {str(e)}")
    except Exception as e:
        error_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{error_timestamp}] ❌ Error in get_monitoring_feedback: {str(e)}")
        print(f"[DEBUG] Error type: {type(e).__name__}")
        print(f"[DEBUG] Full error details: {str(e)}")
        print(f"[DEBUG] Request data at time of error: {request.dict()}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/treatment_protocol_gemini")
async def get_treatment_protocol_feedback(request: TreatmentProtocolRequest):
    """Generate feedback for treatment protocol using Gemini."""
    try:
        print(f"\n[{datetime.now()}] 🔍 Starting treatment protocol feedback generation")
        print(f"[DEBUG] Request data: {request.model_dump_json(indent=2)}")
        
        # Load the case context
        print("[DEBUG] Attempting to load case context...")
        context = await load_case_context(int(request.case_id))
        print(f"[DEBUG] Successfully loaded context length: {len(context)}")
        print(f"[DEBUG] First 100 chars of context: {context[:100]}...")
        
        start_time = datetime.now()
        
        # Configure the model
        model = genai.GenerativeModel('gemini-2.0-flash')
        generation_config = {
            "temperature": 0.7,
            "top_p": 0.8,
            "top_k": 40
        }
        print(f"[DEBUG] Model configuration: {generation_config}")
        
        # Prepare the prompt with the specific inputs
        formatted_prompt = TREATMENT_FEEDBACK_PROMPT.format(
            drug_line=request.drug_line,
            student_reasoning=request.student_reasoning or "No reasoning provided",
            first_line=str(request.first_line),
            case_context=context
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
                "match": "NA",
                "reason": f"Error parsing model response: {str(je)}"
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
        
        # save_result = await save_feedback_response(request.case_id, response_data)
        # response_data["file_path"] = save_result["file_path"]
        
        print(f"[{datetime.now()}] ✅ Successfully generated treatment protocol feedback")
        print(f"[DEBUG] Final response data: {json.dumps(response_data, indent=2)}")
        return response_data

    except json.JSONDecodeError as e:
        error_msg = f"[{datetime.now()}] ❌ JSON parsing error: {str(e)}\n"
        error_msg += f"[DEBUG] Failed JSON content: {response_content}\n"
        error_msg += f"[DEBUG] Exception details: {str(e)}"
        print(error_msg)
        raise HTTPException(status_code=400, detail=error_msg)
    except Exception as e:
        error_msg = f"[{datetime.now()}] ❌ Error in get_treatment_protocol_feedback:\n"
        error_msg += f"[DEBUG] Error type: {type(e).__name__}\n"
        error_msg += f"[DEBUG] Error message: {str(e)}\n"
        error_msg += f"[DEBUG] Request data: {request.model_dump_json()}"
        print(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)
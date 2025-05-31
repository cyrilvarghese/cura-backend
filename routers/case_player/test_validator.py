import asyncio
import json
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import os
from dotenv import load_dotenv
import google.generativeai as genai
from typing import Dict, Any, List, Literal
from enum import Enum
from utils.text_cleaner import clean_code_block
from utils.session_manager import SessionManager
from auth.auth_api import get_user_from_token

# Load environment variables
load_dotenv()

# Define the security scheme
security = HTTPBearer()

# Initialize session manager
session_manager = SessionManager()

# Define TestType enum
class TestType(str, Enum):
    physical_exam = "physical_exam"
    lab_test = "lab_test"

router = APIRouter(
    prefix="/test-validator",
    tags=["test-validation"]
)

class TestValidationRequest(BaseModel):
    case_id: str
    test_type: TestType
    test_name: str

    class Config:
        json_schema_extra = {
            "example": {
                "case_id": "16",
                "test_type": "lab_test",
                "test_name": "Complete Blood Count"
            }
        }

# Initialize the Gemini client
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

async def load_case_context(case_id: str) -> str:
    """Load the case context for the specified case."""
    try:
        file_path = Path(f"case-data/case{case_id}/case_context.md")
        if not file_path.exists():
            # Try alternative file name
            file_path = Path(f"case-data/case{case_id}/case_doc.txt")
            if not file_path.exists():
                print(f"[DEBUG] No case context found for case {case_id}")
                return "No detailed case context available."
        
        with open(file_path, 'r') as file:
            return file.read()
    except Exception as e:
        print(f"[WARNING] Failed to load case context: {str(e)}")
        return "Error loading case context."

def extract_test_names(test_exam_data: Dict[str, Any], test_type: str) -> List[str]:
    """Extract test names based on test type from the test_exam_data."""
    if test_type in test_exam_data:
        return list(test_exam_data[test_type].keys())
    return []

async def load_test_exam_data(case_id: str) -> Dict[str, Any]:
    """Load the test and exam data for the specified case."""
    try:
        file_path = Path(f"case-data/case{case_id}/test_exam_data.json")
        if not file_path.exists():
            print(f"[WARNING] test_exam_data.json not found for case {case_id}")
            return {"physical_exam": {}, "lab_test": {}}
        
        with open(file_path, 'r') as file:
            return json.load(file)
    except json.JSONDecodeError as e:
        print(f"[WARNING] Failed to parse test_exam_data.json for case {case_id}: {str(e)}")
        return {"physical_exam": {}, "lab_test": {}}
    except Exception as e:
        print(f"[WARNING] Failed to load test_exam_data.json for case {case_id}: {str(e)}")
        return {"physical_exam": {}, "lab_test": {}}

def load_prompt(file_path: str) -> str:
    """Load the prompt from a specified file."""
    try:
        with open(file_path, 'r') as file:
            return file.read()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Prompt file not found: {file_path}")

TEST_VALIDATION_PROMPT = load_prompt("prompts/test_validation_v2.md")

@router.post("/validate")
async def validate_test(
    request: TestValidationRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Validate if a test name matches any tests in the case's test_exam_data.json file."""
    try:
        print(f"[{datetime.now()}] 🔍 Validating {request.test_type} test '{request.test_name}' for case {request.case_id}")
        
        # Extract token and authenticate the user
        token = credentials.credentials
        print(f"[DEBUG] Extracted JWT: {token}")
        
        # Get authenticated user
        user_response = await get_user_from_token(token)
        if not user_response["success"]:
            raise HTTPException(status_code=401, detail="Authentication required")
        
        student_id = user_response["user"]["id"]
        
        # Load the test exam data
        print("[DEBUG] Attempting to load test exam data...")
        test_exam_data = await load_test_exam_data(request.case_id)
        print(f"[DEBUG] Successfully loaded test exam data")
        
        # Load case context
        case_context = await load_case_context(request.case_id)
        print(f"[DEBUG] Loaded case context: {len(case_context)} characters")
        
        # Extract test names based on test type
        test_names = extract_test_names(test_exam_data, request.test_type)
        print(f"[DEBUG] Extracted {len(test_names)} {request.test_type} test names")
        
        if not test_names:
            # Store the unmatched test in session
            session_manager.add_test_order(
                student_id=student_id,
                case_id=request.case_id,
                test_type=request.test_type,
                test_name=request.test_name
            )
            return {
                "case_id": request.case_id,
                "test_type": request.test_type,
                "test_name": request.test_name,
                "timestamp": datetime.now().isoformat(),
                "result": {
                    "match": False,
                    "matched_test": None,
                    "reason": f"No {request.test_type} tests found in the case data"
                }
            }
        
        start_time = datetime.now()
        
        # Configure the model
        model = genai.GenerativeModel('gemini-2.0-flash')
        generation_config = {
            "temperature": 0.2,  # Lower temperature for more deterministic responses
            "top_p": 0.95,
            "top_k": 40
        }
        
        # Prepare the prompt
        test_names_json = json.dumps(test_names)
        
        content = {
            "contents": [
                {
                    "parts": [
                        {"text": TEST_VALIDATION_PROMPT},
                        {"text": f"\nCase Context: {case_context}"},
                        {"text": f"\nTest Type: {request.test_type.value}"},
                        {"text": f"\nAvailable Tests: {test_names_json}"},
                        {"text": f"\nUser Input Test: {request.test_name}"}
                    ]
                }
            ],
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
            validation_result = json.loads(cleaned_content)
        except json.JSONDecodeError as je:
            print(f"[DEBUG] JSON parse error: {str(je)}")
            validation_result = {
                "match": False,
                "matched_test": None,
                "reason": f"Error parsing model response: {str(je)}"
            }
        
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        
        # If there's a match, get the full test data and update session
        test_data = None
        final_test_name = request.test_name  # Default to requested name
        
        if validation_result.get("match") and validation_result.get("matched_test"):
            matched_test_name = validation_result["matched_test"]
            if matched_test_name in test_exam_data.get(request.test_type, {}):
                test_data = test_exam_data[request.test_type][matched_test_name]
                final_test_name = matched_test_name  # Use matched name
        
        # Always store the test in session - either matched or unmatched
        session_manager.add_test_order(
            student_id=student_id,
            case_id=request.case_id,
            test_type=request.test_type,
            test_name=final_test_name
        )
        
        response_data = {
            "case_id": request.case_id,
            "test_type": request.test_type,
            "test_name": final_test_name,  # Use final test name here
            "student_id": student_id,
            "timestamp": datetime.now().isoformat(),
            "result": validation_result,
            "test_data": test_data,
            "metadata": {
                "processing_time_seconds": processing_time,
                "model_version": model.model_name,
                "generation_config": generation_config
            }
        }
        
        print(f"[{datetime.now()}] ✅ Successfully validated test")
        return response_data

    except Exception as e:
        error_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        error_msg = f"[{error_timestamp}] ❌ Error in validate_test:\n"
        error_msg += f"[DEBUG] Error type: {type(e).__name__}\n"
        error_msg += f"[DEBUG] Error message: {str(e)}\n"
        error_msg += f"[DEBUG] Request data: {request.model_dump_json()}"
        print(error_msg)
        raise HTTPException(status_code=500, detail=str(e)) 
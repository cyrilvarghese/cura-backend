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
from auth.auth_api import get_user, get_user_from_token

# Load environment variables
load_dotenv()

# Initialize session manager
session_manager = SessionManager()

# Define TestType enum
class TestType(str, Enum):
    physical_exam = "physical_exam"
    lab_test = "lab_test"

# Define the security scheme
security = HTTPBearer()

router = APIRouter(
    prefix="/test-validator",
    tags=["case-player"]
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
    test_data: dict,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Validate test data against case requirements.
    """
    print(f"[TEST_VALIDATOR] 🔍 Validating test data")
    
    # Extract token and authenticate the user
    try:
        token = credentials.credentials  # This is the raw JWT
        print(f"[DEBUG] Extracted JWT: {token}")
        
        print(f"[TEST_VALIDATOR] 🔐 Authenticating user...")
        user_response = await get_user_from_token(token)
        if not user_response["success"]:
            error_message = user_response.get("error", "Authentication required")
            print(f"[TEST_VALIDATOR] ❌ Authentication failed: {error_message}")
            raise HTTPException(status_code=401, detail=error_message)
        
        user_id = user_response["user"]["id"]
        print(f"[TEST_VALIDATOR] ✅ User authenticated successfully. User ID: {user_id}")
        
        try:
            # Your existing validation logic here
            # ... existing code ...
            return {"message": "Test validation completed successfully"}
        except Exception as e:
            print(f"[TEST_VALIDATOR] ❌ Error in test validation: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error in test validation: {str(e)}")
            
    except HTTPException as auth_error:
        print(f"[TEST_VALIDATOR] ❌ HTTP exception during authentication: {str(auth_error)}")
        raise auth_error
    except Exception as auth_error:
        print(f"[TEST_VALIDATOR] ❌ Unexpected error during authentication: {str(auth_error)}")
        raise HTTPException(status_code=401, detail="Authentication failed") 
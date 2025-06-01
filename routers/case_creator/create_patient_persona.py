import json
from fastapi import APIRouter, Form, HTTPException, File, UploadFile, Depends
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from datetime import datetime
import uuid
import os
from dotenv import load_dotenv
from pathlib import Path
from typing import Optional, Any
from utils.case_utils import get_next_case_id
from utils.pdf_utils import extract_text_from_document
from pydantic import BaseModel, model_validator
from routers.case_creator.helpers.save_data_to_file import save_patient_persona
import re
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from auth.auth_api import get_user_from_token
import asyncio
import google.generativeai as genai
from utils.text_cleaner import clean_code_block
import gc  # For garbage collection

# Load environment variables
load_dotenv()

# Configure Gemini
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

# Define the security scheme
security = HTTPBearer()

router = APIRouter(
    prefix="/patient_persona",
    tags=["create-data"]
)

# Initialize the model
model = ChatOpenAI(
    model_name="gpt-4o-mini",
    temperature=0.7,
    api_key=os.getenv("OPENAI_API_KEY")
)

# Add async model for better timeout handling
async_model = ChatOpenAI(
    model_name="gpt-4o-mini",
    temperature=0.7,
    api_key=os.getenv("OPENAI_API_KEY")
)

class PatientPersonaRequest(BaseModel):
    persona_prompt: str

class CreatePersonaRequest(BaseModel):
    file_name: Optional[str] = None
    google_doc_link: Optional[str] = None
    department: Optional[str] = None #to fix make this dept ID instead of name
    case_id: Optional[Any] = None

def load_meta_prompt(file_path: str) -> str:
    """Load the meta prompt from a specified file."""
    try:
        with open(file_path, 'r') as file:
            return file.read()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Meta prompt file not found.")

def load_example_persona(file_path: str) -> str:
    """Load the example persona from a specified file."""
    try:
        with open(file_path, 'r') as file:
            return file.read()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Example persona file not found.")

def save_case_document(case_id: Any, case_document: str) -> str:
    """Save the extracted case document to a text file and return the file path."""
    case_folder = f"case-data/case{case_id}"
    os.makedirs(case_folder, exist_ok=True)
    case_doc_path = os.path.join(case_folder, "case_doc.txt")

    with open(case_doc_path, 'w') as case_doc_file:
        case_doc_file.write(case_document)
    
    return case_doc_path

def save_case_cover(case_id: Any, filename: str, department: str, google_doc_link: Optional[str] = None) -> str:
    """Save the case cover data to a JSON file and return the file path."""
    case_name = create_case_name(filename)
    case_folder = f"case-data/case{case_id}"
    case_cover_data = {
        "case_name": case_name,
        "case_id": case_id,
        "department": department,
        "published": False,
        "google_doc_link": google_doc_link
    }
    print(f"case_cover_data: {case_cover_data}")
    
    case_cover_path = os.path.join(case_folder, "case_cover.json")
    with open(case_cover_path, 'w') as json_file:
        json.dump(case_cover_data, json_file, indent=4)
    
    return case_cover_path

def create_case_name(filename: str) -> str:
    """Generate a cause name from the filename, replacing spaces with underscores."""
    base_name = os.path.splitext(os.path.basename(filename))[0]
    return base_name.replace(" ", "_") + ".md" #.md is used to locate the physical file

async def process_patient_persona(case_document: str, case_id: Any, filename: str, department: str, google_doc_link: Optional[str] = None):
    """Common processing logic for both routes"""
    try:
        # Load prompts
        meta_prompt = load_meta_prompt("prompts/meta_prompts/patient_persona.txt")
        example_persona = load_example_persona("prompts/examples/example_patient_persona.txt")
        
        # Save case document and cover
        case_folder = f"case-data/case{case_id}"
        os.makedirs(case_folder, exist_ok=True)
        save_case_document(case_id, case_document)
        save_case_cover(case_id, filename, department, google_doc_link)

        # Create prompt and get response with timeout handling
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", meta_prompt),
            ("human", "Example Persona:\n{example_persona}\n\nCase Details:\n{case_document}")
        ])
        
        # Use async API call with timeout (120 seconds)
        try:
            response = await asyncio.wait_for(
                async_model.ainvoke(prompt_template.invoke({
                    "example_persona": example_persona,
                    "case_document": case_document
                })),
                timeout=90.0  # Reduced to 90 seconds to prevent hanging
            )
        except asyncio.TimeoutError:
            print(f"[{datetime.now()}] ⏰ OpenAI API call timed out after 90 seconds, trying with shorter document...")
            # Try again with truncated document
            truncated_doc = case_document[:50000] + "\n[Document truncated due to timeout]"
            try:
                response = await asyncio.wait_for(
                    async_model.ainvoke(prompt_template.invoke({
                        "example_persona": example_persona,
                        "case_document": truncated_doc
                    })),
                    timeout=60.0  # Even shorter timeout for retry
                )
                print(f"[{datetime.now()}] ✅ Retry with truncated document succeeded")
            except asyncio.TimeoutError:
                print(f"[{datetime.now()}] ❌ Retry also timed out")
                raise HTTPException(status_code=504, detail="AI processing timed out. Document may be too complex. Please try with a shorter document.")
        
        # Clean up memory
        gc.collect()
        
        escaped_content = response.content.replace("{", "{{").replace("}", "}}")
        
        # Save the persona
        request = PatientPersonaRequest(persona_prompt=escaped_content)
        save_result = await save_patient_persona(case_id, request)
        
        return {
            "id": str(uuid.uuid4()),
            "content": escaped_content,
            "timestamp": datetime.now().isoformat(),
            "type": "ai",
            "file_path": save_result["file_path"],
            "case_id": case_id
        }

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        error_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{error_timestamp}] ❌ Error in process_patient_persona: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/create")
async def create_patient_persona(
    request: CreatePersonaRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Create patient persona data based on a case document.
    """
    start_time = datetime.now()
    print(f"[{start_time}] 🚀 Starting patient persona creation for file: {request.file_name}, case_id: {request.case_id}")
    
    # Extract token and authenticate the user
    try:
        token = credentials.credentials  # This is the raw JWT
        print(f"[DEBUG] Extracted JWT: {token}")
        
        print(f"[PATIENT_PERSONA] 🔐 Authenticating user...")
        user_response = await get_user_from_token(token)
        if not user_response["success"]:
            error_message = user_response.get("error", "Authentication required")
            print(f"[PATIENT_PERSONA] ❌ Authentication failed: {error_message}")
            raise HTTPException(status_code=401, detail=error_message)
        
        user_id = user_response["user"]["id"]
        user_role = user_response["user"].get("role", "")
        
        # Check if user is admin or teacher
        if user_role not in ["admin", "teacher"]:
            print(f"[PATIENT_PERSONA] ❌ Access denied: User role '{user_role}' is not authorized")
            raise HTTPException(status_code=403, detail="Only teachers and admins can create patient personas")
            
        auth_time = datetime.now()
        auth_duration = (auth_time - start_time).total_seconds()
        print(f"[PATIENT_PERSONA] ✅ User authenticated successfully in {auth_duration:.2f}s. User ID: {user_id}, Role: {user_role}")
    except HTTPException as auth_error:
        print(f"[PATIENT_PERSONA] ❌ HTTP exception during authentication: {str(auth_error)}")
        raise auth_error
    except Exception as auth_error:
        print(f"[PATIENT_PERSONA] ❌ Unexpected error during authentication: {str(auth_error)}")
        raise HTTPException(status_code=401, detail="Authentication failed")

    try:
        # Get the uploads directory path from environment variable with fallback
        uploads_dir = Path(os.getenv("UPLOADS_DIR", "case-data/uploads"))
        
        # Convert the incoming filename to a safe version by:
        # - Keeping only alphanumeric characters, hyphens, underscores, and dots
        # - Replacing all other characters with underscores
        # This matches the same safe filename convention used when files are uploaded
        filename = re.sub(r'[^a-zA-Z0-9-_.]', '_', request.file_name)
        
        # Construct the full file path in the uploads directory
        file_path = uploads_dir / filename
        
        print(f"[PATIENT_PERSONA] 📁 Looking for file: {file_path}")

        # Check if the file exists, if not return a 404 error
        if not file_path.exists():
            print(f"[PATIENT_PERSONA] ❌ File not found: {file_path}")
            raise HTTPException(status_code=404, detail=f"File not found in uploads directory: {filename}")

        # Check file size to prevent memory issues
        file_size = file_path.stat().st_size
        max_file_size = 50 * 1024 * 1024  # 50MB limit
        if file_size > max_file_size:
            print(f"[PATIENT_PERSONA] ❌ File too large: {file_size / 1024 / 1024:.2f}MB")
            raise HTTPException(status_code=413, detail=f"File too large. Maximum size is {max_file_size / 1024 / 1024:.0f}MB")

        class FileWrapper:
            def __init__(self, filepath):
                self.filename = Path(filepath).name
                self.file = open(filepath, 'rb')

        try:
            print(f"[PATIENT_PERSONA] 📄 Extracting text from document...")
            file_wrapper = FileWrapper(file_path)
            case_document = extract_text_from_document(file_wrapper)
            file_wrapper.file.close()
            
            # Check document length to prevent timeout
            doc_length = len(case_document)
            max_doc_length = 100000  # 100k characters
            if doc_length > max_doc_length:
                print(f"[PATIENT_PERSONA] ⚠️ Document is very long: {doc_length} characters, truncating...")
                case_document = case_document[:max_doc_length] + "\n[Document truncated due to length]"
            
            extraction_time = datetime.now()
            extraction_duration = (extraction_time - auth_time).total_seconds()
            print(f"[PATIENT_PERSONA] ✅ Text extracted in {extraction_duration:.2f}s. Document length: {len(case_document)} characters")
            
        except IOError as e:
            print(f"[PATIENT_PERSONA] ❌ Failed to read file: {str(e)}")
            raise HTTPException(status_code=400, detail=f"Failed to read file: {str(e)}")

        case_id = request.case_id if request.case_id is not None else get_next_case_id()
        department = request.department
        google_doc_link = request.google_doc_link
        
        print(f"[PATIENT_PERSONA] 🤖 Starting AI processing...")
        result = await process_patient_persona(case_document, case_id, filename, department, google_doc_link)
        
        end_time = datetime.now()
        total_duration = (end_time - start_time).total_seconds()
        print(f"[PATIENT_PERSONA] ✅ Patient persona created successfully in {total_duration:.2f}s")
        
        return result

    except Exception as e:
        error_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        total_duration = (datetime.now() - start_time).total_seconds()
        print(f"[{error_timestamp}] ❌ Error in create_patient_persona after {total_duration:.2f}s: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
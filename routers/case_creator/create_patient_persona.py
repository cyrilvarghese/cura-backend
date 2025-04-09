import json
from fastapi import APIRouter, Form, HTTPException, File, UploadFile
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

# Load environment variables
load_dotenv()

router = APIRouter(
    prefix="/patient_persona",
    tags=["create-data"]
)

# Initialize the model
model = ChatOpenAI(
    model_name="gpt-4o-mini",
    temperature=1,
    api_key=os.getenv("OPENAI_API_KEY")
)

class PatientPersonaRequest(BaseModel):
    persona_prompt: str

class CreatePersonaRequest(BaseModel):
    file_name: Optional[str] = None
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

def save_case_cover(case_id: Any, filename: str, department: str) -> str:
    """Save the case cover data to a JSON file and return the file path."""
    case_name = create_case_name(filename)
    case_folder = f"case-data/case{case_id}"
    case_cover_data = {
        "case_name": case_name,
        "case_id": case_id,
        "department": department,
        "published": False
    }
    
    case_cover_path = os.path.join(case_folder, "case_cover.json")
    with open(case_cover_path, 'w') as json_file:
        json.dump(case_cover_data, json_file, indent=4)
    
    return case_cover_path

def create_case_name(filename: str) -> str:
    """Generate a cause name from the filename, replacing spaces with underscores."""
    base_name = os.path.splitext(os.path.basename(filename))[0]
    return base_name.replace(" ", "_") + ".md" #.md is used to locate the physical file

async def process_patient_persona(case_document: str, case_id: Any, filename: str, department: str):
    """Common processing logic for both routes"""
    try:
        # Load prompts
        meta_prompt = load_meta_prompt("prompts/meta_prompts/patient_persona.txt")
        example_persona = load_example_persona("prompts/examples/example_patient_persona.txt")
        
        # Save case document and cover
        case_folder = f"case-data/case{case_id}"
        os.makedirs(case_folder, exist_ok=True)
        save_case_document(case_id, case_document)
        save_case_cover(case_id, filename, department)

        # Create prompt and get response
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", meta_prompt),
            ("human", "Example Persona:\n{example_persona}\n\nCase Details:\n{case_document}")
        ])
        
        response = model.invoke(prompt_template.invoke({
            "example_persona": example_persona,
            "case_document": case_document
        }))
        
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

    except Exception as e:
        error_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{error_timestamp}] ❌ Error in process_patient_persona: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

 

@router.post("/create")
async def create_patient_persona(request: CreatePersonaRequest):
    """Create a patient persona from a file name."""
    try:
        # Get the uploads directory path
        uploads_dir = Path("uploads")
        
        # Convert the incoming filename to a safe version by:
        # - Keeping only alphanumeric characters, hyphens, underscores, and dots
        # - Replacing all other characters with underscores
        # This matches the same safe filename convention used when files are uploaded
        filename = re.sub(r'[^a-zA-Z0-9-_.]', '_', request.file_name)
        
        # Construct the full file path in the uploads directory
        file_path = uploads_dir / filename

        # Check if the file exists, if not return a 404 error
        if not file_path.exists():
            raise HTTPException(status_code=404, detail=f"File not found in uploads directory: {filename}")

        class FileWrapper:
            def __init__(self, filepath):
                self.filename = Path(filepath).name
                self.file = open(filepath, 'rb')

        try:
            file_wrapper = FileWrapper(file_path)
            case_document = extract_text_from_document(file_wrapper)
            file_wrapper.file.close()
        except IOError as e:
            raise HTTPException(status_code=400, detail=f"Failed to read file: {str(e)}")

        case_id = request.case_id if request.case_id is not None else get_next_case_id()
        department = request.department
        return await process_patient_persona(case_document, case_id, filename, department)

    except Exception as e:
        error_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{error_timestamp}] ❌ Error in create_patient_persona_from_url: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
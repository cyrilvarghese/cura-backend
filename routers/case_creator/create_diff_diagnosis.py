import json
from typing import Optional
from fastapi import APIRouter, File, UploadFile, HTTPException, Form
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from datetime import datetime
import os
from dotenv import load_dotenv
from utils.pdf_utils import extract_text_from_document
from utils.case_utils import get_next_case_id
from utils.text_cleaner import extract_code_blocks
from routers.case_creator.helpers.save_data_to_file import save_differential_diagnosis
from pathlib import Path
from pydantic import BaseModel
import uuid
import re

# Load environment variables
load_dotenv()

router = APIRouter(
    prefix="/differential_diagnosis",
    tags=["create-data"]
)

# Initialize the model
model = ChatOpenAI(
    model_name="gpt-4o-mini",
    temperature=0.7,
    api_key=os.getenv("OPENAI_API_KEY")
)

def load_prompt(file_path: str) -> str:
    """Load the meta prompt from a specified file."""
    try:
        with open(file_path, 'r') as file:
            return file.read()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Meta prompt file not found.")

class CreateDiffDiagnosisRequest(BaseModel):
    file_name: str
    case_id: Optional[int] = None

@router.post("/create")
async def create_differential_diagnosis(request: CreateDiffDiagnosisRequest):
    """Create differential diagnosis based on a case document."""
    try:
        # Get the uploads directory path
        uploads_dir = Path(os.getenv("UPLOADS_DIR", "case-data/uploads"))
        
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

        # Load the meta prompt
        prompt = load_prompt("prompts/diagnosis_context.txt")
        
        # Escape curly braces in the meta prompt
        prompt = prompt.replace("{", "{{").replace("}", "}}")
        
        # If no case_id provided, get the next available one
        if request.case_id is None:
            case_id = get_next_case_id()
        else:
            case_id = request.case_id
        
        # Define the chat prompt template
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", prompt),
            ("human", "Case Details:\n{case_document}")
        ])
        
        # Call the model
        response = model.invoke(prompt_template.invoke({
            "case_document": case_document
        }))
        
        # Extract and parse the JSON response
        response_data = response.content
        cleaned_response = json.loads(extract_code_blocks(response_data)[0])
        
        # Save the differential diagnosis data
        result = await save_differential_diagnosis(case_id, cleaned_response)
        
        # Format the response
        formatted_response = {
            "case_id": case_id,
            "content": cleaned_response,
            "file_path": result["file_path"],
            "timestamp": datetime.now().isoformat(),
            "type": "ai"
        }
        
        return formatted_response

    except Exception as e:
        error_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{error_timestamp}] ❌ Error in create_differential_diagnosis: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

class CreateDiffDiagnosisFromUrlRequest(BaseModel):
    file_url: str
    case_id: int

def save_case_document(case_id: Optional[int], case_document: str) -> str:
    """Save the extracted case document to a text file and return the file path."""
    case_folder = f"case-data/case{case_id}"
    os.makedirs(case_folder, exist_ok=True)
    case_doc_path = os.path.join(case_folder, "case_doc.txt")

    with open(case_doc_path, 'w') as case_doc_file:
        case_doc_file.write(case_document)
    
    return case_doc_path

def save_case_cover(case_id: Optional[int], filename: str) -> str:
    """Save the case cover data to a JSON file and return the file path."""
    case_name = create_case_name(filename)
    case_folder = f"case-data/case{case_id}"
    case_cover_data = {
        "case_name": case_name,
        "case_id": case_id
    }
    
    case_cover_path = os.path.join(case_folder, "case_cover.json")
    with open(case_cover_path, 'w') as json_file:
        json.dump(case_cover_data, json_file, indent=4)
    
    return case_cover_path

def create_case_name(filename: str) -> str:
    """Generate a case name from the filename, replacing spaces with underscores."""
    base_name = os.path.splitext(os.path.basename(filename))[0]
    return base_name.replace(" ", "_")

@router.post("/create-from-url")
async def create_differential_diagnosis_from_url(request: CreateDiffDiagnosisFromUrlRequest):
    """Create differential diagnosis based on a case document from URL."""
    try:
        # Get the filename from the URL and look for it in uploads directory
        uploads_dir = Path(os.getenv("UPLOADS_DIR", "case-data/uploads"))
        filename = Path(request.file_url).name
        file_path = uploads_dir / filename

        if not file_path.exists() or request.case_id is None:
            raise HTTPException(status_code=404, detail=f"File not found in uploads directory or case_id is None: {filename}")

        # Load the meta prompt
        prompt = load_prompt("prompts/differential_diagnosis.txt")
        prompt = prompt.replace("{", "{{").replace("}", "}}")
        
        # Create a file-like object that mimics UploadFile structure
        class FileWrapper:
            def __init__(self, filepath):
                self.filename = Path(filepath).name
                self.file = open(filepath, 'rb')

        # Extract text from the file in uploads directory
        try:
            file_wrapper = FileWrapper(file_path)
            case_document = extract_text_from_document(file_wrapper)
            file_wrapper.file.close()
        except IOError as e:
            raise HTTPException(status_code=400, detail=f"Failed to read file: {str(e)}")

        # Get case_id
        case_id = request.case_id  

        # # Save the case document and cover
        # case_folder = f"case-data/case{case_id}"
        # os.makedirs(case_folder, exist_ok=True)
        # save_case_document(case_id, case_document)
        # save_case_cover(case_id, filename)
        
        # Define the chat prompt template
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", prompt),
            ("human", "Case Details:\n{case_document}")
        ])
        
        # Call the model
        response = model.invoke(prompt_template.invoke({
            "case_document": case_document
        }))
        
        # Extract and parse the JSON response
        response_data = response.content
        cleaned_response = json.loads(extract_code_blocks(response_data)[0])
        
        # Save the differential diagnosis data
        result = await save_differential_diagnosis(case_id, cleaned_response)
        
        # Format the response
        formatted_response = {
            "id": str(uuid.uuid4()),
            "case_id": case_id,
            "content": cleaned_response,
            "file_path": result["file_path"],
            "timestamp": datetime.now().isoformat(),
            "type": "ai"
        }
        
        return formatted_response

    except Exception as e:
        error_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{error_timestamp}] ❌ Error in create_differential_diagnosis_from_url: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) 
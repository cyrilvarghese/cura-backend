import json
from fastapi import APIRouter, HTTPException
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from datetime import datetime
import uuid
import os
from dotenv import load_dotenv
from pathlib import Path
from typing import Optional
from utils.case_utils import get_next_case_id
from utils.pdf_utils import extract_text_from_document
from pydantic import BaseModel
from routers.case_creator.helpers.save_data_to_file import save_patient_persona

# Load environment variables
load_dotenv()

router = APIRouter(
    prefix="/patient_persona_from_url",
    tags=["create-data"]
)

# Initialize the model
model = ChatOpenAI(
    model_name="gpt-4o-mini",
    temperature=1,
    api_key=os.getenv("OPENAI_API_KEY")
)

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

class PatientPersonaRequest(BaseModel):
    persona_prompt: str

class CreatePersonaFromUrlRequest(BaseModel):
    file_url: str
    case_id: Optional[int] = None

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

@router.post("/create")
async def create_patient_persona_from_url(request: CreatePersonaFromUrlRequest):
    """Create a patient persona prompt from a file in the uploads folder."""
    try:
        # Get the filename from the URL and look for it in uploads directory
        uploads_dir = Path("uploads")
        filename = Path(request.file_url).name  # Extract just the filename from the URL
        file_path = uploads_dir / filename

        if not file_path.exists():
            raise HTTPException(status_code=404, detail=f"File not found in uploads directory: {filename}")

        # Load the meta prompt and example persona
        meta_prompt = load_meta_prompt("prompts/meta_prompts/patient_persona.txt")
        example_persona = load_example_persona("prompts/examples/example_patient_persona.txt")
        
        # Create a file-like object that mimics UploadFile structure
        class FileWrapper:
            def __init__(self, filepath):
                self.filename = Path(filepath).name
                self.file = open(filepath, 'rb')

        # Extract text from the file in uploads directory
        try:
            file_wrapper = FileWrapper(file_path)
            case_document = extract_text_from_document(file_wrapper)
            file_wrapper.file.close()  # Make sure to close the file
        except IOError as e:
            raise HTTPException(status_code=400, detail=f"Failed to read file: {str(e)}")

        # Get case_id
        case_id = request.case_id if request.case_id is not None else get_next_case_id()

        # Save the case document
        case_folder = f"case-data/case{case_id}"
        os.makedirs(case_folder, exist_ok=True)
        save_case_document(case_id, case_document)
 
        # Save the case cover JSON file
        save_case_cover(case_id, filename)

        # Define the chat prompt template with placeholders
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", meta_prompt),
            ("human", "Example Persona:\n{example_persona}\n\nCase Details:\n{case_document}")
        ])
        
        # Call the model with the constructed prompt
        response = model.invoke(prompt_template.invoke({
            "example_persona": example_persona,
            "case_document": case_document
        }))
        
        # Escape curly braces in the response content
        escaped_content = response.content.replace("{", "{{").replace("}", "}}")
        
        # Create request object and save the persona
        request = PatientPersonaRequest(persona_prompt=escaped_content)
        save_result = await save_patient_persona(case_id, request)
        
        # Format the response
        formatted_response = {
            "id": str(uuid.uuid4()),
            "content": escaped_content,
            "timestamp": datetime.now().isoformat(),
            "type": "ai",
            "file_path": save_result["file_path"],
            "case_id": case_id
        }
        
        return formatted_response

    except Exception as e:
        error_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{error_timestamp}] ❌ Error in create_patient_persona_from_url: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) 
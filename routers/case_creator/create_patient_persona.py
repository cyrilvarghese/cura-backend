import json
from fastapi import APIRouter, Form, HTTPException, File, UploadFile
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from datetime import datetime
import uuid
import os
from dotenv import load_dotenv
import pdftotext  # Replace PyPDF2 import with pdftotext
import io
from routers.case_creator.helpers.save_data_to_file import save_patient_persona
from pydantic import BaseModel
from pathlib import Path
from typing import Optional
from utils.case_utils import get_next_case_id
from utils.pdf_utils import extract_text_from_pdf  # Import the utility function
# Load environment variables
# create a patient persona prompt and save it using the existing cases route

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



def save_case_document(case_id: Optional[int], case_document: str) -> str:
    """Save the extracted case document to a text file and return the file path."""
    case_folder = f"case-data/case{case_id}"
    os.makedirs(case_folder, exist_ok=True)  # Create the folder if it doesn't exist
    case_doc_path = os.path.join(case_folder, "case_doc.txt")

    # Write the extracted case document to a text file
    with open(case_doc_path, 'w') as case_doc_file:
        case_doc_file.write(case_document)
    
    return case_doc_path  # Return the path of the saved document

def save_case_cover(case_id: Optional[int], pdf_file: UploadFile) -> str:
    """Save the case cover data to a JSON file and return the file path."""
    case_name = create_case_name(pdf_file.filename)
    case_folder = f"case-data/case{case_id}"
    case_cover_data = {
        "case_name": case_name,
        "case_id": case_id
    }
    
    # Define the path for the JSON file
    case_cover_path = os.path.join(case_folder, "case_cover.json")

    # Write the JSON data to a file
    with open(case_cover_path, 'w') as json_file:
        json.dump(case_cover_data, json_file, indent=4)
    
    return case_cover_path  # Return the path of the saved cover data

@router.post("/create")
async def create_patient_persona(pdf_file: UploadFile = File(...), case_id: Optional[int] = Form(None)):
    """Create a patient persona prompt and save it using the existing cases route."""
    try:
        # Load the meta prompt and example persona from their respective files
        meta_prompt = load_meta_prompt("prompts/meta/patient_persona.txt")
        example_persona = load_example_persona("prompts/examples/example_patient_persona.txt")
        
        # Extract text from the uploaded PDF file using the utility function
        case_document = extract_text_from_pdf(pdf_file)

        # Define the path to save the case document
        case_folder = f"case-data/case{case_id}"
        os.makedirs(case_folder, exist_ok=True)  # Create the folder if it doesn't exist
        save_case_document(case_id, case_document)
 
        # Save the case cover JSON file
        save_case_cover(case_id, pdf_file)

        # Define the chat prompt template with placeholders
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", meta_prompt),
            ("human", "Example Persona:\n{example_persona}\n\nCase Details:\n{case_document}")
        ])
        
        # Call the model with the constructed prompt
        response = model.invoke(prompt_template.invoke({
            "example_persona": example_persona,
            "case_document": case_document
        }))  # Pass the variables to fill the placeholders
        
        # Escape curly braces in the response content
        escaped_content = response.content.replace("{", "{{").replace("}", "}}")
        
        # Create request object and call the imported function
        request = PatientPersonaRequest(persona_prompt=escaped_content)
        
        # If no case_id provided, get the next available one
        if case_id is None:
            case_id = get_next_case_id()
        
        # Call the existing endpoint to save the persona
        save_result = await save_patient_persona(case_id, request)
        
        # Combine the AI response with the save result
        formatted_response = {
            "id": str(uuid.uuid4()),
            "content": escaped_content,
            "timestamp": datetime.now().isoformat(),
            "type": "ai",
            "file_path": save_result["file_path"]
        }
        
        return formatted_response

    except Exception as e:
        error_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{error_timestamp}] ❌ Error in create_patient_persona: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

def create_case_name(filename: str) -> str:
    """Generate a case name from the uploaded filename, replacing spaces with underscores."""
    # Extract the base name and replace spaces with underscores
    base_name = os.path.splitext(os.path.basename(filename))[0]
    return base_name.replace(" ", "_")
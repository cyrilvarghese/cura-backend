from fastapi import APIRouter, Form, HTTPException, File, UploadFile
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from datetime import datetime
import uuid
import os
from dotenv import load_dotenv
import pdftotext  # Replace PyPDF2 import with pdftotext
import io
from .create_cases_routes import create_patient_persona as save_patient_persona
from pydantic import BaseModel
from pathlib import Path
from typing import Optional
from utils.case_utils import get_next_case_id
from utils.pdf_utils import extract_text_from_pdf  # Import the utility function
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

@router.post("/create")
async def create_patient_persona(pdf_file: UploadFile = File(...), case_id: Optional[int] = Form(None)):
    """Create a patient persona prompt and save it using the existing cases route."""
    try:
        # Load the meta prompt and example persona from their respective files
        meta_prompt = load_meta_prompt("prompts/meta/patient_persona.txt")
        example_persona = load_example_persona("prompts/examples/example_patient_persona.txt")
        
        # Extract text from the uploaded PDF file using the utility function
        case_document = extract_text_from_pdf(pdf_file)
        
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
from fastapi import APIRouter, File, UploadFile, HTTPException, Form
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from datetime import datetime
import uuid
import os
from dotenv import load_dotenv
import pdftotext  # Library to read PDF files
import io
import json  # Import json for saving data
from pathlib import Path
from utils.case_utils import get_next_case_id  # Import the get_next_case_id function

# Load environment variables
load_dotenv()

router = APIRouter(
    prefix="/exam_test_data",
    tags=["exam-test-data"]
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

def extract_text_from_pdf(pdf_file: UploadFile) -> str:
    """Extract text from a PDF file using pdftotext."""
    try:
        # Read the UploadFile into bytes
        pdf_bytes = pdf_file.file.read()
        
        # Load PDF using pdftotext
        pdf = pdftotext.PDF(io.BytesIO(pdf_bytes))
        
        # Extract text from all pages and join with proper spacing
        text = "\n".join(pdf)
        
        # Clean up the text
        cleaned_text = " ".join(text.split())
        
        return cleaned_text.strip()
        
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Error reading PDF file: {str(e)}"
        )
    finally:
        # Reset file pointer for potential future reads
        pdf_file.file.seek(0)

def save_test_data(case_id: int, data: dict) -> str:
    """Save the test data to a text file."""
    try:
        file_path = f"test_data/case_{case_id}_test_data.json"
        os.makedirs(os.path.dirname(file_path), exist_ok=True)  # Create directory if it doesn't exist
        with open(file_path, 'w') as file:
            json.dump(data, file, indent=4)  # Save data as JSON with indentation
        return file_path
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error saving test data: {str(e)}")

@router.post("/create")
async def create_exam_test_data(pdf_file: UploadFile = File(...), case_id: int = Form(None)):
    """Create exam test data based on a meta prompt and a case document."""
    try:
        # Load the meta prompt from the specified file
        meta_prompt = load_meta_prompt("prompts/meta/exam_test_data.txt")
        
        # Extract text from the uploaded PDF file
        case_document = extract_text_from_pdf(pdf_file)
        
        # If no case_id provided, get the next available one
        if case_id is None:
            case_id = get_next_case_id()
        
        # Define the chat prompt template with placeholders
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", meta_prompt),
            ("human", f"Case Details:\n{case_document}")
        ])
        
        # Call the model with the constructed prompt
        response = model.invoke(prompt_template.invoke({
            "case_document": case_document
        }))  # Pass the variables to fill the placeholders
        
        # Parse the response content into structured JSON
        structured_response = {
            "physical_exam": {},  # Placeholder for physical examination data
            "lab_test": {}        # Placeholder for lab test data
        }
        
        # Assuming the response content is in JSON format
        response_data = response.content
        
        # Populate the structured response
        if isinstance(response_data, dict):
            structured_response["physical_exam"] = response_data.get("physical_exam", {})
            structured_response["lab_test"] = response_data.get("lab_test", {})
        
        # Save the structured response to a text file
        file_path = save_test_data(case_id, structured_response)
        
        # Format response as a dict
        formatted_response = {
         
            "case_id": case_id,
            "data": structured_response,
            "file_path": file_path,
            "timestamp": datetime.now().isoformat(),
            "type": "ai"
        }
        
        return formatted_response

    except Exception as e:
        error_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{error_timestamp}] ❌ Error in create_exam_test_data: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) 
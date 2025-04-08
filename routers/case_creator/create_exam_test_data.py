from typing import Optional
from fastapi import APIRouter, File, UploadFile, HTTPException, Form
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from datetime import datetime
import uuid
import os
from dotenv import load_dotenv
from utils.pdf_utils import extract_text_from_document  # Import the utility function
import io
import json  # Import json for saving data
from pathlib import Path
from utils.case_utils import get_next_case_id
from utils.text_cleaner import extract_code_blocks  # Import the get_next_case_id function
from routers.case_creator.helpers.save_data_to_file import save_examination_data
from pydantic import BaseModel
import re
# Load environment variables
load_dotenv()


# create a exam test data prompt and save it using the existing cases route



router = APIRouter(
    prefix="/exam_test_data",
    tags=["create-data"]
)

# Initialize the model
model = ChatOpenAI(
    model_name="gpt-4o-mini",
    temperature=1,
    api_key=os.getenv("OPENAI_API_KEY")
)

def load_prompt(file_path: str) -> str:
    """Load the meta prompt from a specified file."""
    try:
        with open(file_path, 'r') as file:
            return file.read()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Meta prompt file not found.")

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

class CreateExamTestDataRequest(BaseModel):
    file_name: str
    case_id: Optional[int] = None

@router.post("/create")
async def create_exam_test_data(request: CreateExamTestDataRequest):
    """Create exam test data based on a meta prompt and a case document."""
    try:
        print(f"[{datetime.now()}] Starting exam test data creation for file: {request.file_name}, case_id: {request.case_id}")
        
        uploads_dir = Path("uploads")
        
        # Convert the incoming filename to a safe version by:
        # - Keeping only alphanumeric characters, hyphens, underscores, and dots
        # - Replacing all other characters with underscores
        # This matches the same safe filename convention used when files are uploaded
        filename = re.sub(r'[^a-zA-Z0-9-_.]', '_', request.file_name)
        
        # Construct the full file path in the uploads directory
        file_path = uploads_dir / filename

        print(f"[{datetime.now()}] Attempting to read file from: {file_path}")

        if not file_path.exists():
            print(f"[{datetime.now()}] ❌ File not found: {file_path}")
            raise HTTPException(status_code=404, detail=f"File not found in uploads directory: {filename}")

        class FileWrapper:
            def __init__(self, filepath):
                self.filename = Path(filepath).name
                self.file = open(filepath, 'rb')

        try:
            file_wrapper = FileWrapper(file_path)
            case_document = extract_text_from_document(file_wrapper)
            file_wrapper.file.close()
            print(f"[{datetime.now()}] ✅ Successfully extracted text from document")
        except IOError as e:
            print(f"[{datetime.now()}] ❌ Failed to read file: {str(e)}")
            raise HTTPException(status_code=400, detail=f"Failed to read file: {str(e)}")

        print(f"[{datetime.now()}] Loading meta prompt...")
        prompt = load_prompt("prompts/exam_test_data2.txt")
        
        # Escape curly braces in the meta prompt
        prompt = prompt.replace("{", "{{").replace("}", "}}")
        
        # Define the chat prompt template with placeholders
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", prompt),
            ("human", "Case Details:\n{case_document}")
        ])
        
        print(f"[{datetime.now()}] Calling AI model...")
        response = model.invoke(prompt_template.invoke({
            "case_document": case_document 
        }))
        print(f"[{datetime.now()}] ✅ Received response from AI model")
        
        print(f"[{datetime.now()}] Processing AI response...")
        response_data = response.content
        cleaned_response = json.loads(extract_code_blocks(response_data)[0])
        print(f"[{datetime.now()}] ✅ Successfully processed AI response")
        
        # Parse the response content into structured JSON
        structured_response = {
            "physical_exam": {},  # Placeholder for physical examination data
            "lab_test": {}        # Placeholder for lab test data
        }
        
        # Populate the structured response
        if isinstance(cleaned_response, dict):
            structured_response["physical_exam"] = cleaned_response.get("physical_exam", {})
            structured_response["lab_test"] = cleaned_response.get("lab_test", {})
            structured_response["validation"] = cleaned_response.get("validation", {})
        
        # Save the structured response to a text file
        result = await save_examination_data(request.case_id, structured_response)
        
        # Format response as a dict
        formatted_response = {
            "case_id": request.case_id,
            "content": structured_response,
            "file_path": result["file_path"],
            "timestamp": datetime.now().isoformat(),
            "type": "ai"
        }
        
        print(f"[{datetime.now()}] ✅ Successfully completed exam test data creation")
        return formatted_response

    except Exception as e:
        error_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{error_timestamp}] ❌ Error in create_exam_test_data: {str(e)}")
        print(f"[{error_timestamp}] ❌ Error type: {type(e).__name__}")
        print(f"[{error_timestamp}] ❌ Error details: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
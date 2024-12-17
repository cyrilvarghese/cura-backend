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

@router.post("/create")
async def create_differential_diagnosis(
    file: UploadFile = File(...), 
    case_id: Optional[int] = Form(None)
):
    """Create differential diagnosis based on a case document."""
    try:
        # Load the meta prompt
        prompt = load_prompt("prompts/differential_diagnosis.txt")
        
        # Escape curly braces in the meta prompt
        prompt = prompt.replace("{", "{{").replace("}", "}}")
        
        # Extract text from the uploaded file
        case_document = extract_text_from_document(file)
        
        # If no case_id provided, get the next available one
        if case_id is None:
            case_id = get_next_case_id()
        
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
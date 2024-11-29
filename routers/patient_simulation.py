from fastapi import APIRouter, HTTPException
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from typing import Dict, Any
import json
from datetime import datetime
import uuid
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

router = APIRouter(
    prefix="/patient",
    tags=["patient-simulation"]
)

def load_prompt_template():
    """Load the prompt template from file"""
    try:
        with open("prompts/patient_persona.txt", "r") as file:
            return file.read()
    except FileNotFoundError:
        raise Exception("Prompt template file not found")

# Initialize the model
model = ChatOpenAI(
    model_name="gpt-4o-mini",
    temperature=1,
    api_key=os.getenv("OPENAI_API_KEY")
)

# Create prompt template with variable
system_template = load_prompt_template()
prompt_template = ChatPromptTemplate.from_messages([
    ("system", system_template),
    ("human", "{student_query}")
])

def parse_llm_response(response_content: str) -> Dict[str, Any]:
    """Parse the LLM response and extract the JSON content"""
    try:
        # First try to parse the entire response
        parsed_response = json.loads(response_content)
        
        # If the content field contains a JSON string, parse that too
        if isinstance(parsed_response.get("content"), str):
            try:
                content_json = json.loads(parsed_response["content"])
                return content_json
            except json.JSONDecodeError:
                return parsed_response
        return parsed_response
    except json.JSONDecodeError as e:
        # If parsing fails, return a default formatted response
        return {
            "id": str(uuid.uuid4()),
            "sender": "Patient",
            "content": response_content,
            "step": "patient-history",
            "timestamp": datetime.now().isoformat(),
            "type": "text"
        }

@router.get("/ask")
async def ask_patient(student_query: str):
    """
    Ask a question to the simulated patient.
    
    Args:
        student_query: The question to ask the patient
    
    Returns:
        dict: Contains the patient's response in the specified format
    """
    try:
        # Get response from the model
        response = model.invoke(prompt_template.invoke({
            "student_query": student_query
        }))

        # Parse and format the response
        formatted_response = parse_llm_response(response.content)
        
        return formatted_response

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 
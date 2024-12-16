import json
from fastapi import APIRouter, Form, HTTPException, File, UploadFile
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableSequence
from langchain_community.utilities.dalle_image_generator import DallEAPIWrapper
from datetime import datetime
import uuid
import os
from dotenv import load_dotenv
from utils.pdf_utils import extract_text_from_pdf
from utils.text_cleaner import extract_code_blocks  # Import the utility function
# create a cover image prompt and save it using the existing cases route

# Load environment variables
load_dotenv()

router = APIRouter(
    prefix="/cover_image",
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

def load_patient_persona(case_id: int) -> str:
    """Load the patient persona based on the case ID."""
    file_path = f"case-data/case{case_id}/patient_prompts/patient_persona.txt"
    try:
        with open(file_path, 'r') as file:
            return file.read()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Patient persona file for case {case_id} not found.")

@router.post("/create")
async def create_cover_image(case_id: str, prompt: str | None = None):
    """
    Create a cover image based on either a direct prompt or by generating one from the case document.
    
    Args:
        case_id (str): The ID of the case
        prompt (str, optional): Direct prompt for DALL-E. If provided, skips GPT prompt generation
    """
    try:
        formatted_response = {}
        
        if prompt:
            # If prompt is provided, directly use it for DALL-E
            image_url = DallEAPIWrapper(model="dall-e-3").run(prompt)
            formatted_response = {
                "prompt": prompt,
                "image_url": image_url,
                "title": None,
                "quote": None
            }
        else:
            # Existing flow for generating prompt using GPT
            meta_prompt = load_meta_prompt("prompts/meta/cover_image_prompt1.txt")
            patient_persona = load_patient_persona(case_id)
            
            prompt_template = ChatPromptTemplate.from_messages([
                ("system", meta_prompt),
                ("human", "Create a cover image prompt based on the following patient persona:\n{patient_persona}")
            ])
            
            chain = prompt_template | model
            cover_image_prompt = chain.invoke({"patient_persona": patient_persona})
            cleaned_response = extract_code_blocks(cover_image_prompt.content)
            responseJSON = json.loads(cleaned_response[0])
            
            image_prompt = responseJSON["image_prompt"]
            title = responseJSON["title"]
            quote = responseJSON["quote"]
            
            image_url = DallEAPIWrapper(model="dall-e-3").run(image_prompt)
            
            formatted_response = {
                "prompt": image_prompt,
                "image_url": image_url,
                "title": title,
                "quote": quote
            }

        formatted_log = (
            f"Cover image prompt generated successfully.\n"
            f"Prompt: {formatted_response['prompt']}\n"
            f"Image URL: {formatted_response['image_url']}"
        )
        print(formatted_log)
        
        return formatted_response

    except Exception as e:
        error_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{error_timestamp}] ❌ Error in create_cover_image: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) 
import json
from typing import Optional
from fastapi import APIRouter, Form, HTTPException, File, UploadFile, Request
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableSequence
from langchain_community.utilities.dalle_image_generator import DallEAPIWrapper
from datetime import datetime
import uuid
import os
from dotenv import load_dotenv
from pydantic import BaseModel
import urllib3
from routers.case_creator.helpers.image_downloader import download_image
from utils.pdf_utils import extract_text_from_document
from utils.text_cleaner import extract_code_blocks  # Import the utility function
# create a cover image prompt and save it using the existing cases route
from fastapi import Request

async def get_server_host_url(request: Request) -> str:
    """Retrieve the current server host URL."""
    return f"{request.scheme}://{request.headers['host']}"

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

# update the case cover data in the JSON file       
def update_case_cover(case_id: str, title: str, quote: str, image_url: str) -> None:
    """Update the case cover data in the JSON file."""
    case_folder = f"case-data/case{case_id}"
    case_cover_path = os.path.join(case_folder, "case_cover.json")
    
    # Read the existing case cover data
    with open(case_cover_path, 'r') as json_file:
        case_cover_data = json.load(json_file)
    
    # Update the title, quote, and image URL
    case_cover_data["title"] = title
    case_cover_data["quote"] = quote
    case_cover_data["image_url"] = image_url
    
    # Write the updated JSON data back to the file
    with open(case_cover_path, 'w') as json_file:
        json.dump(case_cover_data, json_file, indent=4)

async def call_image_gen(case_id: str, image_prompt: str, hasPrompt: bool = False) -> str:
    """Generate or retrieve the image URL for the case cover."""
    case_folder = f"case-data/case{case_id}"
    case_cover_path = os.path.join(case_folder, "case_cover.json")
    
    # Load the case cover data
    with open(case_cover_path, 'r') as json_file:
        case_cover_data = json.load(json_file)
    
    # Check if we need to generate a new image or 
    if "image_url" not in case_cover_data  or hasPrompt:
        # Generate new image with DALL-E
        dalle_image_url = DallEAPIWrapper(model="dall-e-3").run(image_prompt)
        # Download the image
        image_path = os.path.join(case_folder, "cover_image.png")
        await download_image(dalle_image_url, image_path)
        server_image_url = f"/case-images/case{case_id}/cover_image.png"
    else:
        server_image_url = case_cover_data["image_url"]
    
    return server_image_url

class CoverImageRequest(BaseModel):
    prompt: Optional[str] = None
    title: Optional[str] = None
    quote: Optional[str] = None 

@router.post("/create")
async def create_cover_image(
    case_id: str,  # Required parameter
    cover_data: Optional[CoverImageRequest] = None,
    request: Request = None
):
    # Access optional fields with default values
    prompt = cover_data.prompt if cover_data else None
    title = cover_data.title if cover_data else None
    quote = cover_data.quote if cover_data else None
    
    try:
        formatted_response = {}
        server_host_url = str(request.base_url).rstrip('/')
        if cover_data and cover_data.prompt:
            # Generate image using provided prompt
            image_url = await call_image_gen(case_id, cover_data.prompt, True)
            
            title = cover_data.title
            quote = cover_data.quote
            formatted_response = {
                "prompt": cover_data.prompt,
                "image_url": image_url,
                "title": title,
                "quote": quote
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
            
            image_url = await call_image_gen(case_id, image_prompt,)
            
            formatted_response = {
                "prompt": image_prompt,
                "image_url": image_url,
                "title": title,
                "quote": quote
            }
          
        
        update_case_cover(case_id, title, quote, image_url)

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
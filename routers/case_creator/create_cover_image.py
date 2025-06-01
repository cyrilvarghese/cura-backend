import json
from typing import Optional
from fastapi import APIRouter, HTTPException, Request
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.utilities.dalle_image_generator import DallEAPIWrapper
from datetime import datetime
import os
from dotenv import load_dotenv
from pydantic import BaseModel
from routers.case_creator.helpers.image_downloader import download_image
from utils.text_cleaner import extract_code_blocks  # Import the utility function
import asyncio


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

def load_prompt(file_path: str) -> str:
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
def update_case_cover(case_id: str, title: str, quote: str, image_url: str, image_prompt: str) -> None:
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
    case_cover_data["image_prompt"] = image_prompt
    # Write the updated JSON data back to the file
    with open(case_cover_path, 'w') as json_file:
        json.dump(case_cover_data, json_file, indent=4)

async def call_image_gen(case_id: str, image_prompt: str, hasPrompt: bool = False) -> str:
    """Generate or retrieve the image URL for the case cover."""
    case_folder = f"case-data/case{case_id}"
    case_cover_path = os.path.join(case_folder, "case_cover.json")
    
    # Add timestamp for cache busting
    timestamp = int(datetime.now().timestamp())
    
    # Load the case cover data
    with open(case_cover_path, 'r') as json_file:
        case_cover_data = json.load(json_file)
    
    # Check if we need to generate a new image or if the image is not present
    if "image_url" not in case_cover_data or hasPrompt:
        dalle_image_url = await asyncio.to_thread(
            DallEAPIWrapper(model="dall-e-3").run, 
            image_prompt
        )
        image_path = os.path.join(case_folder, "cover_image.png")
        await download_image(dalle_image_url, image_path)
        server_image_url = f"/case-images/case{case_id}/cover_image.png?v={timestamp}"
    else:
        # Replace existing timestamp instead of appending
        base_url = case_cover_data['image_url'].split('?')[0]
        server_image_url = f"{base_url}?v={timestamp}"
    
    return server_image_url

class CoverImageRequest(BaseModel):
    case_id: str
    prompt: Optional[str] = None
    title: Optional[str] = None
    quote: Optional[str] = None

class PhraseRequest(BaseModel):
    phrase: str

@router.post("/generate")
async def create_cover_image(
    cover_data: CoverImageRequest,
    request: Request = None
):
    try:
        formatted_response = {}
        image_prompt = None  # Initialize image_prompt variable
        
        if cover_data.prompt:
            # Generate image using provided prompt
            image_prompt = cover_data.prompt
            image_url = await call_image_gen(cover_data.case_id, image_prompt, True)
            
            formatted_response = {
                "prompt": image_prompt,
                "image_url": image_url,
                "title": cover_data.title,
                "quote": cover_data.quote
            }
        else:
            # Existing flow for generating prompt using GPT
            prompt = load_prompt("prompts/cover_image_prompt1.txt")
            patient_persona = load_patient_persona(cover_data.case_id)
            
            prompt_template = ChatPromptTemplate.from_messages([
                ("system", prompt),
                ("human", "Create a cover image prompt based on the following patient persona:\n{patient_persona}")
            ])
            
            chain = prompt_template | model
            cover_image_prompt = chain.invoke({"patient_persona": patient_persona})
            cleaned_response = extract_code_blocks(cover_image_prompt.content)
            responseJSON = json.loads(cleaned_response[0])
            
            image_prompt = responseJSON["image_prompt"]
            title = responseJSON["title"]
            quote = responseJSON["quote"]
            
            image_url = await call_image_gen(cover_data.case_id, image_prompt)
            
            formatted_response = {
                "prompt": image_prompt,
                "image_url": image_url,
                "title": title,
                "quote": quote
            }
        
        update_case_cover(cover_data.case_id, formatted_response["title"], formatted_response["quote"], formatted_response["image_url"], image_prompt)
        return formatted_response

    except Exception as e:
        error_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{error_timestamp}] ❌ Error in create_cover_image: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

def update_case_cover_phrases(case_folder: str, phrase: str) -> list:
    """
    Update the phrases to avoid in case_cover.json
    
    Args:
        case_folder (str): Path to the case folder
        phrase (str): New phrase to add to avoid list
    
    Returns:
        list: Updated list of phrases to avoid
    
    Raises:
        HTTPException: If case_cover.json is not found or other errors occur
    """
    case_cover_path = os.path.join(case_folder, "case_cover.json")
    if not os.path.exists(case_cover_path):
        raise HTTPException(
            status_code=404, 
            detail=f"Case cover data not found at {case_cover_path}"
        )
    
    with open(case_cover_path, 'r') as json_file:
        case_cover_data = json.load(json_file)
    
    if "phrases_to_avoid" not in case_cover_data:
        case_cover_data["phrases_to_avoid"] = []
    
    if phrase not in case_cover_data["phrases_to_avoid"]:
        case_cover_data["phrases_to_avoid"].append(phrase)
    
    with open(case_cover_path, 'w') as json_file:
        json.dump(case_cover_data, json_file, indent=4)
    
    return case_cover_data["phrases_to_avoid"]

def update_patient_persona_phrases(case_folder: str, phrase: str) -> None:
    """
    Update or create the "Words and Phrases to Avoid" section in patient_persona.txt
    just above the Response Format section.
    
    Args:
        case_folder (str): Path to the case folder
        phrase (str): New phrase to add to avoid list
    
    Raises:
        HTTPException: If patient_persona.txt is not found or other errors occur
    """
    persona_path = os.path.join(case_folder, "patient_prompts", "patient_persona.txt")
    if not os.path.exists(persona_path):
        raise HTTPException(
            status_code=404,
            detail=f"Patient persona file not found at {persona_path}"
        )

    with open(persona_path, 'r') as file:
        content = file.read()

    # Format new phrase as bullet point
    new_phrase_bullet = f"- \"{phrase}\"\n"

    if "#### Words and Phrases to Avoid" in content:
        # Section exists, add new phrase if it's not already there
        sections = content.split("#### Words and Phrases to Avoid")
        before_section = sections[0]
        after_section = sections[1].split("#### Response Format")
        
        if new_phrase_bullet not in after_section[0]:
            # Add the new phrase to the existing section
            updated_content = (
                before_section +
                "#### Words and Phrases to Avoid\n\n" +
                after_section[0].rstrip() + "\n" +
                new_phrase_bullet + "\n" +
                "#### Response Format" +
                after_section[1]
            )
            
            with open(persona_path, 'w') as file:
                file.write(updated_content)
    else:
        # Create new section just above Response Format
        sections = content.split("#### Response Format")
        if len(sections) != 2:
            raise HTTPException(
                status_code=400,
                detail="Could not find Response Format section"
            )
        
        updated_content = (
            sections[0].rstrip() +
            "\n\n#### Words and Phrases to Avoid\n\n" +
            new_phrase_bullet + "\n\n" +
            "#### Response Format" +
            sections[1]
        )
        
        with open(persona_path, 'w') as file:
            file.write(updated_content)

@router.post("/{case_id}/add-phrase-to-avoid")
async def add_phrase_to_avoid(case_id: str, phrase_data: PhraseRequest):
    """Add a phrase to avoid to both case cover data and patient persona."""
    try:
        case_folder = f"case-data/case{case_id}"
        
        # Check if the case folder exists
        if not os.path.exists(case_folder):
            raise HTTPException(
                status_code=404, 
                detail=f"Case {case_id} not found. Please ensure the case exists."
            )
        
        # Update both files
        updated_phrases = update_case_cover_phrases(case_folder, phrase_data.phrase)
        update_patient_persona_phrases(case_folder, phrase_data.phrase)

        return {
            "message": "Phrase added successfully to both case cover and patient persona",
            "phrases_to_avoid": updated_phrases
        }

    except HTTPException:
        raise
    except Exception as e:
        error_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{error_timestamp}] ❌ Error in add_phrase_to_avoid: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
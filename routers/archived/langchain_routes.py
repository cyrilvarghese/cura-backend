from fastapi import APIRouter, HTTPException
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from typing import Optional
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

router = APIRouter(
    prefix="/translate",
    tags=["translation"]
)

# Initialize the model
model = ChatOpenAI(
    model_name="gpt-3.5-turbo",
    temperature=1,
    api_key=os.getenv("OPENAI_API_KEY")
)

# Create a translation prompt template
system_template = "Translate the following from English into {language}"
prompt_template = ChatPromptTemplate.from_messages([
    ("system", system_template),
    ("user", "{text}")
])

@router.get("/")
async def translate_text(text: str, language: str):
    """
    Translate text from English to specified language.
    
    Args:
        text: The English text to translate
        language: The target language for translation
    
    Returns:
        dict: Contains the translated text and status
    """
    try:
        # Format the prompt with the input
        prompt = prompt_template.invoke({
            "language": language,
            "text": text
        })

        # Get the response from the model
        response = model.invoke(prompt)

        return {
            "translation": response.content,
            "status": "success",
            "original_text": text,
            "target_language": language
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 
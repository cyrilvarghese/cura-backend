from fastapi import APIRouter, HTTPException
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from typing import Dict, Any
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
    temperature=0.7,
    api_key=os.getenv("OPENAI_API_KEY")
)

# Create a translation prompt template
system_template = "Translate the following from English into {language}"
prompt_template = ChatPromptTemplate.from_messages([
    ("system", system_template),
    ("user", "{text}")
])

@router.post("/")
async def translate_text(request: Dict[str, Any]):
    try:
        # Validate input
        if "text" not in request or "language" not in request:
            raise HTTPException(
                status_code=400, 
                detail="Both 'text' and 'language' are required"
            )

        # Format the prompt with the input
        prompt = prompt_template.invoke({
            "language": request["language"],
            "text": request["text"]
        })

        # Get the response from the model
        response = model.invoke(prompt)

        return {
            "translation": response.content,
            "status": "success"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 
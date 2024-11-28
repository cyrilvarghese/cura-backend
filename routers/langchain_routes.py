from fastapi import APIRouter, HTTPException
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langgraph.graph import MessageGraph
from typing import Dict, Any
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

router = APIRouter(
    prefix="/chat",
    tags=["chat"]
)

# Initialize OpenAI model
model = ChatOpenAI(
    model="gpt-3.5-turbo",
    temperature=0.7,
    api_key=os.getenv("OPENAI_API_KEY")
)

# Create a simple chat graph
workflow = MessageGraph()
workflow.add_node("chat", model)
workflow.set_entry_point("chat")

# Create a prompt template
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful AI assistant."),
    ("human", "{input}")
])

@router.post("/")
async def chat_endpoint(message: Dict[str, Any]):
    try:
        # Validate input
        if "input" not in message:
            raise HTTPException(status_code=400, detail="Input message is required")

        # Process the message through the graph
        chain = prompt | workflow
        response = chain.invoke({"input": message["input"]})
        
        return {
            "response": response.content,
            "status": "success"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 
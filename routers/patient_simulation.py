from fastapi import APIRouter, HTTPException
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, MessagesState, StateGraph
from typing import Dict, Any
import json
from datetime import datetime
import uuid
import os
from dotenv import load_dotenv
import logging
from utils.text_cleaner import clean_code_block

# Load environment variables
load_dotenv()

router = APIRouter(
    prefix="/patient",
    tags=["patient-simulation"]
)
 

def load_prompt_template():
    """Load the prompt template from file"""
    try:
        with open("case-data/case1/patient_prompts/patient_persona.txt", "r") as file:
            return file.read()
    except FileNotFoundError:
        raise Exception("Prompt template file not found")

# Initialize the model
model = ChatOpenAI(
    model_name="gpt-4o-mini",
    temperature=1,
    api_key=os.getenv("OPENAI_API_KEY")
)

# Create prompt template with system message and message history
system_template = load_prompt_template()
prompt = ChatPromptTemplate.from_messages([
    ("system", system_template),
    MessagesPlaceholder(variable_name="messages")
])

# Create the chain
chain = prompt | model

# Define the graph workflow
workflow = StateGraph(MessagesState)

def call_model(state: MessagesState):
    """Process the message through the model and return response"""
    response = chain.invoke(state)
    
    # Format response as a dict with metadata
    formatted_response = {
        "id": str(uuid.uuid4()),
        "sender": "Patient",
        "content": response.content,
        "step": "patient-history",
        "timestamp": datetime.now().isoformat(),
        "type": "ai"
    }
    
    return {"messages": formatted_response}

# Add the model node to the graph
workflow.add_edge(START, "model")
workflow.add_node("model", call_model)

# Initialize memory
memory = MemorySaver()
app = workflow.compile(checkpointer=memory)

@router.get("/ask")
async def ask_patient(student_query: str, thread_id: str = None):
    try:
        if not thread_id:
            thread_id = str(uuid.uuid4())   
        
        input_message = HumanMessage(content=student_query)
        response = app.invoke(
            {"messages": [input_message]}, 
            config={"configurable": {"thread_id": thread_id}}
        )
        
        # Get content and clean code block markers
        content = clean_code_block(response['messages'][-1].content)
        
        # Print in specified format
        print(f"Thread ID: {thread_id}")
        print(f"Message: {content}")
        print("="*50)
        
        return {
            "response": content,
            "thread_id": thread_id
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 
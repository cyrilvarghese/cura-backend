from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, MessagesState, StateGraph
from typing import Dict, Any, AsyncIterator
import json
from datetime import datetime
import uuid
import os
from dotenv import load_dotenv
import logging
from utils.text_cleaner import clean_code_block
import asyncio

# Load environment variables
load_dotenv()

router = APIRouter(
    prefix="/patient",
    tags=["patient-simulation"]
)
 

def load_prompt_template(case_id: str = "case2"):
    """Load the prompt template from file"""
    try:
        file_path = f"case-data/{case_id}/patient_prompts/patient_persona.txt"
        with open(file_path, "r") as file:
            return file.read()
    except FileNotFoundError:
        raise Exception(f"Prompt template file not found for case: {case_id}")

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

# Initialize streaming model
streaming_model = ChatOpenAI(
    model_name="gpt-4-mini",
    temperature=1,
    streaming=True,  # Enable streaming
    api_key=os.getenv("OPENAI_API_KEY")
)

# Create streaming prompt template
streaming_prompt = ChatPromptTemplate.from_messages([
    ("system", system_template),
    MessagesPlaceholder(variable_name="messages")
])

# Create streaming chain
streaming_chain = streaming_prompt | streaming_model

@router.get("/ask")
async def ask_patient(student_query: str, case_id: str = "case1", thread_id: str = None):
    try:
        if not thread_id:
            thread_id = str(uuid.uuid4())   
        
        # Reinitialize the chain with the correct case template
        system_template = load_prompt_template(case_id)
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_template),
            MessagesPlaceholder(variable_name="messages")
        ])
        chain = prompt | model
        
        input_message = HumanMessage(content=student_query)
        response = app.invoke(
            {"messages": [input_message]}, 
            config={"configurable": {"thread_id": thread_id}}
        )
        
        # Get content and clean code block markers
        content = clean_code_block(response['messages'][-1].content)
        
        # Print in specified format
        print(f"Thread ID: {thread_id}")
        print(f"Case ID: {case_id}")
        print(f"Message: {content}")
        print("="*50)
        
        return {
            "response": content,
            "thread_id": thread_id,
            "case_id": case_id
        }

    except Exception as e:
        error_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{error_timestamp}] ❌ Error in ask_patient: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) 

@router.get("/ask/stream")
async def stream_patient_response(
    student_query: str, 
    case_id: str = "case1", 
    thread_id: str = None
) -> StreamingResponse:
    """
    Stream the patient's response token by token
    """
    async def generate_response() -> AsyncIterator[str]:
        try:
            if not thread_id:
                current_thread_id = str(uuid.uuid4())
            else:
                current_thread_id = thread_id

            # Initialize with correct case template
            system_template = load_prompt_template(case_id)
            streaming_prompt = ChatPromptTemplate.from_messages([
                ("system", system_template),
                MessagesPlaceholder(variable_name="messages")
            ])
            streaming_chain = streaming_prompt | streaming_model

            input_message = HumanMessage(content=student_query)
            
            # Stream the response
            async for chunk in streaming_chain.astream(
                {"messages": [input_message]}
            ):
                # Clean any code block markers from the chunk
                if hasattr(chunk, 'content'):
                    cleaned_chunk = clean_code_block(chunk.content)
                else:
                    cleaned_chunk = clean_code_block(str(chunk))
                
                # Create a response chunk with metadata
                response_chunk = {
                    "content": cleaned_chunk,
                    "thread_id": current_thread_id,
                    "case_id": case_id,
                    "timestamp": datetime.now().isoformat()
                }
                
                # Yield the chunk as a server-sent event
                yield f"data: {json.dumps(response_chunk)}\n\n"
                
                # Small delay to prevent overwhelming the client
                await asyncio.sleep(0.01)
                
        except Exception as e:
            error_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{error_timestamp}] ❌ Error in stream_patient_response: {str(e)}")
            error_response = {
                "error": str(e),
                "thread_id": current_thread_id,
                "case_id": case_id
            }
            yield f"data: {json.dumps(error_response)}\n\n"
            
        # Send a completion event
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate_response(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream",
        }
    )
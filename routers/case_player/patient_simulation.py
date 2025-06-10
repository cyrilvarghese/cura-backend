from fastapi import APIRouter, HTTPException, Depends
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, MessagesState, StateGraph
from datetime import datetime
import uuid
import os
from dotenv import load_dotenv
from utils.text_cleaner import clean_code_block
from langchain_google_genai import ChatGoogleGenerativeAI, HarmCategory, HarmBlockThreshold
from utils.session_manager import SessionManager
from auth.auth_api import get_user, get_user_from_token
import json
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

# Load environment variables
load_dotenv()

# Define the security scheme
security = HTTPBearer()

router = APIRouter(
    prefix="/patient",
    tags=["case-player"]
)

# Initialize session manager
session_manager = SessionManager()

def load_prompt_template(case_id: str = "1"):
    """Load the prompt template from file"""
    print(f"Loading prompt template for case: {case_id}")
    try:
        file_path = f"case-data/case{case_id}/patient_prompts/patient_persona.txt"
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

# Initialize Gemini model
gemini_model = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",
    temperature=0.7,
    google_api_key=os.getenv("GOOGLE_API_KEY"),
    safety_settings={
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
    }
)

# Define custom state type
class PatientSimState(MessagesState):
    case_id: str  # Add the new field while inheriting messages from MessagesState

# Define the graph workflow for OpenAI
workflow = StateGraph(PatientSimState)

# Define the graph workflow for Gemini
gemini_workflow = StateGraph(PatientSimState)

async def call_gemini_model(state: PatientSimState):
    # Access both messages and case_id
    case_id = state["case_id"]
    
    # Create prompt template with system message and message history
    system_template = load_prompt_template(case_id)
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_template),
        MessagesPlaceholder(variable_name="messages")
    ])

    # Create the chain
    chain = prompt | gemini_model

    response = await chain.ainvoke(state)
    
    # Format response as a dict with metadata
    formatted_response = {
        "id": str(uuid.uuid4()),
        "sender": "Patient",
        "content": response.content,
        "step": "patient-history",
        "timestamp": datetime.utcnow().isoformat() + "Z",  # Use UTC time with Z suffix for ISO 8601
        "type": "ai",
        "case_id": case_id
    }
    
    return {"messages": formatted_response, "case_id": case_id}

# Add the model node to the graph
gemini_workflow.add_edge(START, "model")
gemini_workflow.add_node("model", call_gemini_model)

# Initialize memory for Gemini
gemini_memory = MemorySaver()
gemini_app = gemini_workflow.compile(checkpointer=gemini_memory)

async def call_model(state: PatientSimState):
    # Now we have type-safe access to both messages and case_id
    case_id = state["case_id"]
    
    # Create prompt template with system message and message history
    system_template = load_prompt_template(case_id)
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_template),
        MessagesPlaceholder(variable_name="messages")
    ])

    # Create the chain
    chain = prompt | model

    """Process the message through the model and return response"""
    response = await chain.ainvoke(state)
    
    # Format response as a dict with metadata
    formatted_response = {
        "id": str(uuid.uuid4()),
        "sender": "Patient",
        "content": response.content,
        "step": "patient-history",
        "timestamp": datetime.utcnow().isoformat() + "Z",  # Use UTC time with Z suffix for ISO 8601
        "type": "ai",
        "case_id": case_id
    }
    
    return {"messages": formatted_response, "case_id": case_id}

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

@router.post("/simulate")
async def simulate_patient_response(
    simulation_data: dict,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Simulate patient responses based on the provided data.
    """
    print(f"[PATIENT_SIMULATION] 🤖 Processing simulation request")
    
    # Extract token and authenticate the user
    try:
        token = credentials.credentials  # This is the raw JWT
        print(f"[DEBUG] Extracted JWT: {token}")
        
        print(f"[PATIENT_SIMULATION] 🔐 Authenticating user...")
        user_response = await get_user_from_token(token)
        if not user_response["success"]:
            error_message = user_response.get("error", "Authentication required")
            print(f"[PATIENT_SIMULATION] ❌ Authentication failed: {error_message}")
            raise HTTPException(status_code=401, detail=error_message)
        
        user_id = user_response["user"]["id"]
        print(f"[PATIENT_SIMULATION] ✅ User authenticated successfully. User ID: {user_id}")
        
        try:
            # Your existing simulation logic here
            # ... existing code ...
            return {"message": "Simulation completed successfully"}
        except Exception as e:
            print(f"[PATIENT_SIMULATION] ❌ Error in simulation: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error in simulation: {str(e)}")
            
    except HTTPException as auth_error:
        print(f"[PATIENT_SIMULATION] ❌ HTTP exception during authentication: {str(auth_error)}")
        raise auth_error
    except Exception as auth_error:
        print(f"[PATIENT_SIMULATION] ❌ Unexpected error during authentication: {str(auth_error)}")
        raise HTTPException(status_code=401, detail="Authentication failed")

@router.get("/ask")
async def ask_patient(
    student_query: str,
    case_id: str = "1",
    thread_id: str = None,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Handle patient simulation questions from students.
    """
    print(f"[PATIENT_SIMULATION] 💬 Processing student query for case {case_id}")
    
    # Extract token and authenticate the user
    try:
        token = credentials.credentials  # This is the raw JWT
        print(f"[DEBUG] Extracted JWT: {token}")
        
        print(f"[PATIENT_SIMULATION] 🔐 Authenticating user...")
        user_response = await get_user_from_token(token)
        if not user_response["success"]:
            error_message = user_response.get("error", "Authentication required")
            print(f"[PATIENT_SIMULATION] ❌ Authentication failed: {error_message}")
            raise HTTPException(status_code=401, detail=error_message)
        
        student_id = user_response["user"]["id"]
        print(f"[PATIENT_SIMULATION] ✅ User authenticated successfully. Student ID: {student_id}")
        
        try:
            # Generate thread ID if not provided
            if not thread_id:
                thread_id = str(uuid.uuid4())
            
            # Create properly typed initial state
            initial_state: PatientSimState = {
                "messages": [HumanMessage(content=student_query)],
                "case_id": case_id
            }
            
            # Get response from model
            print(f"[PATIENT_SIMULATION] 🤖 Calling model for response...")
            response = await app.ainvoke(
                initial_state,
                config={"configurable": {"thread_id": thread_id}}
            )
            
            # Parse the response
            print(f"[PATIENT_SIMULATION] 📝 Processing model response...")
            content = clean_code_block(response['messages'][-1].content)
            try:
                response_obj = json.loads(content)
                answer = response_obj.get('content', content)
            except json.JSONDecodeError:
                answer = content
            
            # Track the history-taking question in the session
            session_manager.add_history_question(student_id, case_id, student_query, answer)
            
            # Log interaction details
            print(f"[PATIENT_SIMULATION] ℹ️ Interaction Details:")
            print(f"Thread ID: {thread_id}")
            print(f"Case ID: {case_id}")
            print(f"Student ID: {student_id}")
            print(f"Message: {answer}")
            print("="*50)
            
            print(f"[PATIENT_SIMULATION] ✅ Successfully processed student query")
            return {
                "response": content,
                "thread_id": thread_id,
                "case_id": case_id,
                "student_id": student_id
            }
            
        except Exception as e:
            print(f"[PATIENT_SIMULATION] ❌ Error processing student query: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error processing student query: {str(e)}")
            
    except HTTPException as auth_error:
        print(f"[PATIENT_SIMULATION] ❌ HTTP exception during authentication: {str(auth_error)}")
        raise auth_error
    except Exception as auth_error:
        print(f"[PATIENT_SIMULATION] ❌ Unexpected error during authentication: {str(auth_error)}")
        raise HTTPException(status_code=401, detail="Authentication failed")

@router.get("/ask-gemini")
async def ask_patient_gemini(
    student_query: str, 
    case_id: str = "1", 
    thread_id: str = None,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Handle patient simulation questions from students using Gemini model.
    """
    print(f"[PATIENT_SIMULATION_GEMINI] 💬 Processing student query for case {case_id}")
    
    # Extract token and authenticate the user
    try:
        token = credentials.credentials  # This is the raw JWT
        print(f"[DEBUG] Extracted JWT: {token}")
        
        print(f"[PATIENT_SIMULATION_GEMINI] 🔐 Authenticating user...")
        user_response = await get_user_from_token(token)
        if not user_response["success"]:
            error_message = user_response.get("error", "Authentication required")
            print(f"[PATIENT_SIMULATION_GEMINI] ❌ Authentication failed: {error_message}")
            raise HTTPException(status_code=401, detail=error_message)
        
        student_id = user_response["user"]["id"]
        print(f"[PATIENT_SIMULATION_GEMINI] ✅ User authenticated successfully. Student ID: {student_id}")
        
        try:
            # Generate thread ID if not provided
            if not thread_id:
                thread_id = str(uuid.uuid4())
            
            # Create properly typed initial state
            initial_state: PatientSimState = {
                "messages": [HumanMessage(content=student_query)],
                "case_id": case_id
            }
            
            # Get response from model
            print(f"[PATIENT_SIMULATION_GEMINI] 🤖 Calling Gemini model for response...")
            response = await gemini_app.ainvoke(
                initial_state,
                config={"configurable": {"thread_id": thread_id}}
            )
            
            # Parse the response
            print(f"[PATIENT_SIMULATION_GEMINI] 📝 Processing model response...")
            content = clean_code_block(response['messages'][-1].content)
            try:
                response_obj = json.loads(content)
                answer = response_obj.get('content', content)
            except json.JSONDecodeError:
                answer = content
            
            # Track the history-taking question in the session
            session_manager.add_history_question(student_id, case_id, student_query, answer)
            
            # Log interaction details
            print(f"[PATIENT_SIMULATION_GEMINI] ℹ️ Interaction Details:")
            print(f"Thread ID: {thread_id}")
            print(f"Case ID: {case_id}")
            print(f"Student ID: {student_id}")
            print(f"Message: {answer}")
            print("="*50)
            
            print(f"[PATIENT_SIMULATION_GEMINI] ✅ Successfully processed student query")
            return {
                "response": content,
                "thread_id": thread_id,
                "case_id": case_id,
                "student_id": student_id
            }
            
        except Exception as e:
            print(f"[PATIENT_SIMULATION_GEMINI] ❌ Error processing student query: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error processing student query: {str(e)}")
            
    except HTTPException as auth_error:
        print(f"[PATIENT_SIMULATION_GEMINI] ❌ HTTP exception during authentication: {str(auth_error)}")
        raise auth_error
    except Exception as auth_error:
        print(f"[PATIENT_SIMULATION_GEMINI] ❌ Unexpected error during authentication: {str(auth_error)}")
        raise HTTPException(status_code=401, detail="Authentication failed") 
 
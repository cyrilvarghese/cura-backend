from fastapi import APIRouter, HTTPException
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
from auth.auth_api import get_user
import json

# Load environment variables
load_dotenv()

router = APIRouter(
    prefix="/patient",
    tags=["patient-simulation"]
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

def call_gemini_model(state: PatientSimState):
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

    response = chain.invoke(state)
    
    # Format response as a dict with metadata
    formatted_response = {
        "id": str(uuid.uuid4()),
        "sender": "Patient",
        "content": response.content,
        "step": "patient-history",
        "timestamp": datetime.now().isoformat(),
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

def call_model(state: PatientSimState):
    # Now we have type-safe access to both messages and case_id
    case_id = state["case_id"]
    
    # Create prompt template with system message and message history
    system_template = load_prompt_template(case_id)  # Now passing case_id to load_prompt_template
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_template),
        MessagesPlaceholder(variable_name="messages")
    ])

    # Create the chain
    chain = prompt | model

    """Process the message through the model and return response"""
    response = chain.invoke(state)
    
    # Format response as a dict with metadata
    formatted_response = {
        "id": str(uuid.uuid4()),
        "sender": "Patient",
        "content": response.content,
        "step": "patient-history",
        "timestamp": datetime.now().isoformat(),
        "type": "ai",
        "case_id": case_id  # Include case_id in the response
    }
    
    return {"messages": formatted_response, "case_id": case_id}  # Return both messages and case_id

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
 
@router.get("/ask")
async def ask_patient(student_query: str, case_id: str = "1", thread_id: str = None):
    try:
        if not thread_id:
            thread_id = str(uuid.uuid4())   
        
        # Get authenticated user
        user_response = await get_user()
        if not user_response["success"]:
            raise HTTPException(status_code=401, detail="Authentication required")
        
        student_id = user_response["user"]["id"]
        
        # Create properly typed initial state
        initial_state: PatientSimState = {
            "messages": [HumanMessage(content=student_query)],
            "case_id": case_id
        }
        
        response = app.invoke(
            initial_state,  # Pass the complete state object
            config={"configurable": {"thread_id": thread_id}}
        )
        
        # Parse the JSON string and extract content
        content = clean_code_block(response['messages'][-1].content)
        try:
            response_obj = json.loads(content)
            content = response_obj.get('content', content)  # Fallback to original content if parsing fails
        except json.JSONDecodeError:
            # Keep the original content if JSON parsing fails
            pass
        
        # Track the history-taking question in the session
        session_manager.add_history_question(student_id, case_id, student_query, content)
        
        # Print in specified format
        print(f"Thread ID: {thread_id}")
        print(f"Case ID: {case_id}")
        print(f"Student ID: {student_id}")
        print(f"Message: {content}")
        print("="*50)
        
        return {
            "response": content,
            "thread_id": thread_id,
            "case_id": case_id,
            "student_id": student_id
        }

    except Exception as e:
        error_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{error_timestamp}] ❌ Error in ask_patient: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) 

@router.get("/ask-gemini")
async def ask_patient_gemini(student_query: str, case_id: str = "1", thread_id: str = None):
    try:
        if not thread_id:
            thread_id = str(uuid.uuid4())   
        
        # Get authenticated user
        user_response = await get_user()
        if not user_response["success"]:
            raise HTTPException(status_code=401, detail="Authentication required")
        
        student_id = user_response["user"]["id"]
        
        # Create properly typed initial state
        initial_state: PatientSimState = {
            "messages": [HumanMessage(content=student_query)],
            "case_id": case_id
        }
        
        response = gemini_app.invoke(
            initial_state,
            config={"configurable": {"thread_id": thread_id}}
        )
        
        # Parse the JSON string and extract content
        content = clean_code_block(response['messages'][-1].content)
        try:
            response_obj = json.loads(content)
            answer = response_obj.get('content', content)  # Fallback to original content if parsing fails
        except json.JSONDecodeError:
            # Keep the original content if JSON parsing fails
            pass
        
        # Track the history-taking question in the session
        session_manager.add_history_question(student_id, case_id, student_query, answer)
        
        # Print in specified format
        print(f"Thread ID: {thread_id}")
        print(f"Case ID: {case_id}")
        print(f"Student ID: {student_id}")
        print(f"Message: {answer}")
        print("="*50)
        
        return {
            "response": content,
            "thread_id": thread_id,
            "case_id": case_id,
            "student_id": student_id
        }

    except Exception as e:
        error_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{error_timestamp}] ❌ Error in ask_patient_gemini: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) 
 
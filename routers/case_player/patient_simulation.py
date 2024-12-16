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

# Load environment variables
load_dotenv()

router = APIRouter(
    prefix="/patient",
    tags=["patient-simulation"]
)
 

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


# Define custom state type
class PatientSimState(MessagesState):
    case_id: str  # Add the new field while inheriting messages from MessagesState

# Define the graph workflow♠♠
workflow = StateGraph(PatientSimState)

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
        
        # Create properly typed initial state
        initial_state: PatientSimState = {
            "messages": [HumanMessage(content=student_query)],
            "case_id": case_id
        }
        
        response = app.invoke(
            initial_state,  # Pass the complete state object
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
 
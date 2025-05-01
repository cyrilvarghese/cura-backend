from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException
from datetime import datetime
import os
from dotenv import load_dotenv
import json
from pathlib import Path
import asyncio

# LangChain imports
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain.output_parsers import ResponseSchema, StructuredOutputParser

# Local utility imports
from utils.text_cleaner import clean_code_block
from utils.session_manager import SessionManager
from auth.auth_api import get_user

# Load environment variables
load_dotenv()

# Constants
CASE_DATA_PATH_PATTERN = "case-data/case{}"
DIAGNOSIS_CONTEXT_FILENAME = "diagnosis_context.json"

router = APIRouter(
    prefix="/feedback",
    tags=["diagnosis-feedback-langchain"]
)

# Initialize the SessionManager
session_manager = SessionManager()

def load_prompt(file_path: str) -> str:
    """Load the prompt from a specified file."""
    try:
        with open(file_path, 'r') as file:
            return file.read()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Prompt file not found: {file_path}")

# Load the prompt from file
DIAGNOSIS_FEEDBACK_PROMPT = load_prompt("prompts/diagnosis_feedback.txt")

async def load_diagnosis_context(case_id: int) -> Dict[str, Any]:
    """Load the diagnosis context from the case file."""
    try:
        file_path = Path(f"{CASE_DATA_PATH_PATTERN.format(case_id)}/{DIAGNOSIS_CONTEXT_FILENAME}")
        if not file_path.exists():
            raise FileNotFoundError(f"Diagnosis context not found for case {case_id}")
        
        with open(file_path, 'r') as file:
            return json.load(file)
    except Exception as e:
        raise HTTPException(
            status_code=404, 
            detail=f"Failed to load diagnosis context for case {case_id}: {str(e)}"
        )

async def get_session_data():
    """Helper function to get authenticated user's session data."""
    user_response = await get_user()
    if not user_response["success"]:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    student_id = user_response["user"]["id"]
    session_data = session_manager.get_session(student_id)
    if not session_data:
        raise HTTPException(status_code=404, detail="No active session found")
    
    return student_id, session_data

def prepare_student_input(session_data: Dict[str, Any]) -> Dict[str, Any]:
    """Prepare student input data from session data for the diagnosis feedback prompt."""
    # Extract physical examinations (array of test_name from physical_examinations array)
    physical_examinations = [
        exam["test_name"] for exam in session_data["interactions"]["physical_examinations"]
    ]
    
    # Extract tests ordered (array of test_name from tests_ordered array)
    tests_ordered = [
        test["test_name"] for test in session_data["interactions"]["tests_ordered"]
    ]
    
    # Extract clinical findings
    clinical_findings = session_data["interactions"]["clinical_findings"]
    
    # Extract diagnosis submission
    diagnosis_submission = session_data["interactions"]["diagnosis_submission"]
    
    # Extract final diagnosis
    final_diagnosis = session_data["interactions"]["final_diagnosis"]
    
    # Prepare the student input JSON
    student_input = {
        "clinical_findings": clinical_findings,
        "physical_examinations": physical_examinations,
        "tests_ordered": tests_ordered,
        "diagnosis_submission": diagnosis_submission,
        "final_diagnosis": final_diagnosis
    }
    
    return student_input

# Define output schemas for diagnosis feedback
def get_diagnosis_output_parser():
    """Create a structured output parser for the diagnosis feedback."""
    schemas = [
        ResponseSchema(name="diagnostic_accuracy", description="Assessment of diagnostic accuracy"),
        ResponseSchema(name="data_interpretation", description="Assessment of data interpretation skills"),
        ResponseSchema(name="differential_diagnosis", description="Assessment of differential diagnosis quality"),
        ResponseSchema(name="clinical_reasoning", description="Assessment of clinical reasoning process"),
        ResponseSchema(name="overall_feedback", description="Overall feedback on diagnostic approach"),
        ResponseSchema(name="improvement_suggestions", description="Suggestions for improvement")
    ]
    return StructuredOutputParser.from_response_schemas(schemas)

@router.get("/diagnosis/feedback-langchain")
async def get_diagnosis_feedback_langchain():
    """Generate detailed feedback on student's diagnostic process using LangChain."""
    try:
        print(f"\n[{datetime.now()}] 🔍 Starting LangChain diagnosis feedback generation")
        
        # Get session data
        student_id, session_data = await get_session_data()
        case_id = session_data["case_id"]
        
        # Load diagnosis context
        diagnosis_context = await load_diagnosis_context(int(case_id))
        
        # Prepare student input data
        student_input = prepare_student_input(session_data)
        
        # Initialize LangChain components
        llm = ChatOpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            model="gpt-4o",
            temperature=0.7
        )
        
        # Format the prompt for LangChain
        prompt_template = PromptTemplate(
            input_variables=["diagnosis_context", "student_input"],
            template=DIAGNOSIS_FEEDBACK_PROMPT
        )
        
        # Create LangChain chain
        diagnosis_chain = LLMChain(
            llm=llm,
            prompt=prompt_template
        )
        
        # Execute the chain
        start_time = datetime.now()
        print(f"[{datetime.now()}] 🔄 Executing LangChain for diagnosis feedback...")
        
        response = await asyncio.to_thread(
            diagnosis_chain.invoke,
            {
                "diagnosis_context": json.dumps(diagnosis_context, indent=2),
                "student_input": json.dumps(student_input, indent=2)
            }
        )
        
        print(f"[{datetime.now()}] ✅ Received response from LangChain")
        
        # Process and return the response
        raw_response = response["text"]
        cleaned_content = clean_code_block(raw_response)
        feedback_result = json.loads(cleaned_content)
        
        # Save feedback to session
        try:
            # Use the session manager method to add feedback
            session_manager.add_diagnosis_feedback(
                student_id=student_id,
                feedback_result=feedback_result
            )
            print(f"[DEBUG] Successfully saved diagnosis feedback to session")
        except Exception as save_error:
            print(f"[WARNING] Failed to save diagnosis feedback to session: {str(save_error)}")
        
        return {
            "case_id": case_id,
            "student_id": student_id,
            "timestamp": datetime.now().isoformat(),
            "feedback_result": feedback_result,
            "metadata": {
                "processing_time_seconds": (datetime.now() - start_time).total_seconds(),
                "model_version": "gpt-4o",
                "source": "langchain"
            }
        }
        
    except Exception as e:
        error_msg = f"Error in get_diagnosis_feedback_langchain: {str(e)}"
        print(f"[{datetime.now()}] ❌ {error_msg}")
        print(f"[{datetime.now()}] ❌ Error type: {type(e).__name__}")
        print(f"[{datetime.now()}] ❌ Error details: {str(e)}")
        import traceback
        print(f"[{datetime.now()}] ❌ Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=error_msg) 
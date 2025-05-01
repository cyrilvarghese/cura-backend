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
HISTORY_CONTEXT_FILENAME = "history_context.json"

router = APIRouter(
    prefix="/feedback",
    tags=["history-feedback-langchain"]
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

# Load the prompts from files
HISTORY_ANALYSIS_PROMPT = load_prompt("prompts/history_analysis_v3.md")  # Prompt 1
HISTORY_AETCOM_PROMPT = load_prompt("prompts/history_aetcom.txt")      # Prompt 2

async def load_case_context(case_id: int) -> str:
    """Load the case context from the case file."""
    try:
        file_path = Path(f"{CASE_DATA_PATH_PATTERN.format(case_id)}/{HISTORY_CONTEXT_FILENAME}")
        if not file_path.exists():
            raise FileNotFoundError(f"Case document not found for case {case_id}")
        
        with open(file_path, 'r') as file:
            data = json.load(file)
            # Format the JSON as a more readable string for the LLM
            case_summary = data["case_summary_history"]
            formatted_text = ""
            
            for key, value in case_summary.items():
                if isinstance(value, dict):
                    formatted_text += f"\n{key.replace('_', ' ').title()}:\n"
                    for sub_key, sub_value in value.items():
                        if sub_value is not None:
                            formatted_text += f"  - {sub_key.replace('_', ' ').title()}: {sub_value}\n"
                elif isinstance(value, list):
                    formatted_text += f"\n{key.replace('_', ' ').title()}:\n"
                    for item in value:
                        formatted_text += f"  - {item}\n"
                else:
                    formatted_text += f"\n{key.replace('_', ' ').title()}: {value}\n"
            
            return formatted_text
    except Exception as e:
        raise HTTPException(
            status_code=404, 
            detail=f"Failed to load context for case {case_id}: {str(e)}"
        )

async def load_expected_questions(case_id: int) -> List[str]:
    """Load the expected questions from the history context file."""
    try:
        file_path = Path(f"{CASE_DATA_PATH_PATTERN.format(case_id)}/{HISTORY_CONTEXT_FILENAME}")
        if not file_path.exists():
            raise FileNotFoundError(f"History context not found for case {case_id}")
        
        with open(file_path, 'r') as file:
            data = json.load(file)
            # Extract just the expected_questions array from the JSON
            if "expected_questions" in data:
                return data["expected_questions"]
            else:
                raise ValueError("No 'expected_questions' field found in history context file")
    except Exception as e:
        raise HTTPException(
            status_code=404,
            detail=f"Failed to load expected questions for case {case_id}: {str(e)}"
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

# Define output schemas for each analysis component
def get_analysis_output_parser():
    """Create a structured output parser for the history analysis step."""
    schemas = [
        ResponseSchema(name="overall_score", description="Overall score out of 10"),
        ResponseSchema(name="question_coverage", description="Assessment of questions asked vs expected"),
        ResponseSchema(name="question_quality", description="Assessment of question phrasing and clarity"),
        ResponseSchema(name="question_sequencing", description="Assessment of logical flow of questions"),
        ResponseSchema(name="missed_areas", description="Key areas missed in history taking"),
        ResponseSchema(name="detailed_feedback", description="Comprehensive qualitative feedback")
    ]
    return StructuredOutputParser.from_response_schemas(schemas)

def get_aetcom_output_parser():
    """Create a structured output parser for the AETCOM feedback step."""
    schemas = [
        ResponseSchema(name="empathy_score", description="Score for empathy shown"),
        ResponseSchema(name="communication_score", description="Score for communication effectiveness"),
        ResponseSchema(name="professionalism_score", description="Score for professional behavior"),
        ResponseSchema(name="rapport_building", description="Assessment of rapport building"),
        ResponseSchema(name="specific_feedback", description="Specific actionable feedback"),
        ResponseSchema(name="improvement_areas", description="Areas that need improvement")
    ]
    return StructuredOutputParser.from_response_schemas(schemas)

@router.get("/history-taking/analysis-langchain")
async def get_history_analysis():
    """Step 1: Generate detailed analysis and overall score using LangChain."""
    try:
        print(f"\n[{datetime.now()}] 🔍 Starting LangChain history analysis generation (Step 1)")
        
        # Get session data
        student_id, session_data = await get_session_data()
        case_id = session_data["case_id"]
        
        # Load required data
        context = await load_case_context(int(case_id))
        expected_questions = await load_expected_questions(int(case_id))
        
        # Get student questions
        student_questions = [
            {
                "question": interaction["question"],
                "response": interaction["response"]
            }
            for interaction in session_data["interactions"]["history_taking"]
        ]
        
        # Initialize LangChain components
        llm = ChatOpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            model="gpt-4o",
            temperature=0.7
        )
        
        # Format the prompt for LangChain
        prompt_template = PromptTemplate(
            input_variables=["case_context", "expected_questions", "student_questions"],
            template=HISTORY_ANALYSIS_PROMPT
        )
        
        # Create LangChain chain
        analysis_chain = LLMChain(
            llm=llm,
            prompt=prompt_template
        )
        
        # Execute the chain
        start_time = datetime.now()
        response = await asyncio.to_thread(
            analysis_chain.invoke,
            {
                "case_context": context,
                "expected_questions": json.dumps(expected_questions, indent=2),
                "student_questions": json.dumps(student_questions, indent=2)
            }
        )
        
        # Process and return the response
        raw_response = response["text"]
        cleaned_content = clean_code_block(raw_response)
        analysis_result = json.loads(cleaned_content)
        
        # Add analysis_result to session
        session_manager.add_history_analysis(student_id, analysis_result)
        print(f"[DEBUG] Successfully saved analysis results to session")
        
        return {
            "case_id": case_id,
            "student_id": student_id,
            "timestamp": datetime.now().isoformat(),
            "analysis_result": analysis_result,
            "metadata": {
                "processing_time_seconds": (datetime.now() - start_time).total_seconds(),
                "model_version": "gpt-4-turbo",
                "source": "langchain"
            }
        }
        
    except Exception as e:
        error_msg = f"Error in get_history_analysis with LangChain: {str(e)}"
        print(f"[{datetime.now()}] ❌ {error_msg}")
        raise HTTPException(status_code=500, detail=error_msg)

@router.get("/history-taking/aetcom-langchain")
async def get_history_aetcom_feedback():
    """Step 2: Generate domain scores and final feedback using LangChain."""
    try:
        print(f"\n[{datetime.now()}] 🔍 Starting LangChain AETCOM feedback generation (Step 2)")
        
        # Get session data
        try:
            student_id, session_data = await get_session_data()
            print(f"[{datetime.now()}] ✅ Retrieved session data for student ID: {student_id}")
            case_id = session_data["case_id"]
            print(f"[{datetime.now()}] ✅ Working with case ID: {case_id}")
        except Exception as session_error:
            print(f"[{datetime.now()}] ❌ Error retrieving session data: {str(session_error)}")
            print(f"[{datetime.now()}] ❌ Error details: {type(session_error).__name__}")
            raise
        
        # Get analysis results from session
        try:
            if "feedback" not in session_data["interactions"]:
                print(f"[{datetime.now()}] ⚠️ 'feedback' key not found in session_data['interactions']")
                print(f"[{datetime.now()}] ⚠️ Available keys: {list(session_data['interactions'].keys())}")
                raise HTTPException(
                    status_code=400,
                    detail="Analysis results not found in session. Please run the analysis step first."
                )
            
            if "history_taking" not in session_data["interactions"]["feedback"]:
                print(f"[{datetime.now()}] ⚠️ 'history_taking' key not found in session_data['interactions']['feedback']")
                print(f"[{datetime.now()}] ⚠️ Available keys: {list(session_data['interactions']['feedback'].keys())}")
                raise HTTPException(
                    status_code=400,
                    detail="Analysis results not found in session. Please run the analysis step first."
                )
                
            if "analysis" not in session_data["interactions"]["feedback"]["history_taking"]:
                print(f"[{datetime.now()}] ⚠️ 'analysis' key not found in session_data['interactions']['feedback']['history_taking']")
                print(f"[{datetime.now()}] ⚠️ Available keys: {list(session_data['interactions']['feedback']['history_taking'].keys())}")
                raise HTTPException(
                    status_code=400,
                    detail="Analysis results not found in session. Please run the analysis step first."
                )
                
            analysis_result = session_data["interactions"]["feedback"]["history_taking"]["analysis"]
            print(f"[{datetime.now()}] ✅ Successfully retrieved analysis results from session")
        except KeyError as key_error:
            print(f"[{datetime.now()}] ❌ KeyError accessing session data: {str(key_error)}")
            print(f"[{datetime.now()}] ❌ Session data structure: {json.dumps(session_data, indent=2)[:500]}...")
            raise HTTPException(
                status_code=400,
                detail=f"Missing key in session data: {str(key_error)}"
            )
       
        # Load required data
        try:
            context = await load_case_context(int(case_id))
            print(f"[{datetime.now()}] ✅ Loaded case context, length: {len(context)} characters")
            expected_questions = await load_expected_questions(int(case_id))
            print(f"[{datetime.now()}] ✅ Loaded {len(expected_questions)} expected questions")
        except Exception as load_error:
            print(f"[{datetime.now()}] ❌ Error loading case data: {str(load_error)}")
            print(f"[{datetime.now()}] ❌ Error details: {type(load_error).__name__}")
            raise
        
        # Get student questions
        try:
            student_questions = [
                {
                    "question": interaction["question"],
                    "response": interaction["response"]
                }
                for interaction in session_data["interactions"]["history_taking"]
            ]
            print(f"[{datetime.now()}] ✅ Extracted {len(student_questions)} student questions")
        except Exception as extract_error:
            print(f"[{datetime.now()}] ❌ Error extracting student questions: {str(extract_error)}")
            print(f"[{datetime.now()}] ❌ Error details: {type(extract_error).__name__}")
            if "interactions" in session_data and "history_taking" in session_data["interactions"]:
                print(f"[{datetime.now()}] ❌ First history_taking item: {json.dumps(session_data['interactions']['history_taking'][0] if session_data['interactions']['history_taking'] else 'empty', indent=2)}")
            raise
        
        # Initialize LangChain components
        try:
            llm = ChatOpenAI(
                api_key=os.getenv("OPENAI_API_KEY"),
                model="gpt-4o",
                temperature=0.7
            )
            print(f"[{datetime.now()}] ✅ Initialized OpenAI ChatModel: gpt-4-turbo")
        except Exception as model_error:
            print(f"[{datetime.now()}] ❌ Error initializing ChatOpenAI: {str(model_error)}")
            print(f"[{datetime.now()}] ❌ Error details: {type(model_error).__name__}")
            raise
        
        # Format the prompt for LangChain
        try:
            prompt_template = PromptTemplate(
                input_variables=["case_context", "expected_questions", "student_questions"],
                template=HISTORY_AETCOM_PROMPT
            )
            print(f"[{datetime.now()}] ✅ Created prompt template for AETCOM feedback")
        except Exception as prompt_error:
            print(f"[{datetime.now()}] ❌ Error creating prompt template: {str(prompt_error)}")
            print(f"[{datetime.now()}] ❌ Error details: {type(prompt_error).__name__}")
            raise
        
        # Create LangChain chain
        aetcom_chain = LLMChain(
            llm=llm,
            prompt=prompt_template
        )
        
        # Execute the chain
        try:
            start_time = datetime.now()
            print(f"[{datetime.now()}] 🔄 Executing LangChain for AETCOM feedback...")
            
            response = await asyncio.to_thread(
                aetcom_chain.invoke,
                {
                    "case_context": context,
                    "expected_questions": json.dumps(expected_questions, indent=2),
                    "student_questions": json.dumps(student_questions, indent=2)
                }
            )
            
            print(f"[{datetime.now()}] ✅ Received response from LangChain")
        except Exception as chain_error:
            print(f"[{datetime.now()}] ❌ Error executing LangChain: {str(chain_error)}")
            print(f"[{datetime.now()}] ❌ Error details: {type(chain_error).__name__}")
            raise
        
        # Process and return the response
        try:
            raw_response = response["text"]
            
            # Save raw response to file for debugging
            debug_dir = Path("debug_logs")
            debug_dir.mkdir(exist_ok=True)
            debug_file = debug_dir / f"aetcom_response_{student_id}_{case_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            with open(debug_file, "w") as f:
                f.write(f"RAW RESPONSE:\n{raw_response}\n\n")
            
            cleaned_content = clean_code_block(raw_response)
            
            # Also save cleaned content
            with open(debug_file, "a") as f:
                f.write(f"CLEANED CONTENT:\n{cleaned_content}\n\n")
            
            print(f"[{datetime.now()}] ✅ Cleaned response content, length: {len(cleaned_content)} characters")
            print(f"[{datetime.now()}] ✅ Saved raw and cleaned response to {debug_file}")
            
            # More robust JSON parsing with fallback
            try:
                feedback_result = json.loads(cleaned_content)
                print(f"[{datetime.now()}] ✅ Parsed JSON response successfully")
            except json.JSONDecodeError as json_error:
                print(f"[{datetime.now()}] ⚠️ JSON parsing error: {str(json_error)}")
                print(f"[{datetime.now()}] ⚠️ Attempting to fix JSON...")
                
                # Try to fix common JSON issues
                import re
                
                # Log the error position
                with open(debug_file, "a") as f:
                    f.write(f"JSON ERROR: {str(json_error)}\n")
                    error_pos = int(re.search(r'char (\d+)', str(json_error)).group(1))
                    f.write(f"Error position: {error_pos}\n")
                    f.write(f"Content around error: {cleaned_content[max(0, error_pos-50):min(len(cleaned_content), error_pos+50)]}\n\n")
                
                # Try to fix common JSON issues
                fixed_content = cleaned_content
                # Replace single quotes with double quotes
                fixed_content = re.sub(r"'([^']*)':", r'"\1":', fixed_content)
                # Fix trailing commas in arrays and objects
                fixed_content = re.sub(r",\s*}", "}", fixed_content)
                fixed_content = re.sub(r",\s*\]", "]", fixed_content)
                
                with open(debug_file, "a") as f:
                    f.write(f"FIXED CONTENT:\n{fixed_content}\n\n")
                
                try:
                    feedback_result = json.loads(fixed_content)
                    print(f"[{datetime.now()}] ✅ Parsed fixed JSON successfully")
                except json.JSONDecodeError:
                    # If still failing, create a simplified response
                    print(f"[{datetime.now()}] ⚠️ Still unable to parse JSON, creating fallback response")
                    feedback_result = {
                        "empathy_score": "5/10",
                        "communication_score": "5/10",
                        "professionalism_score": "5/10",
                        "rapport_building": "Unable to parse detailed feedback",
                        "specific_feedback": "The system encountered an error processing the detailed feedback. Please review the raw response for more information.",
                        "improvement_areas": "Unable to parse detailed feedback",
                        "raw_response": raw_response[:1000] + "..." if len(raw_response) > 1000 else raw_response
                    }
        except Exception as parse_error:
            print(f"[{datetime.now()}] ❌ Error processing response: {str(parse_error)}")
            print(f"[{datetime.now()}] ❌ Error details: {type(parse_error).__name__}")
            raise
        
        # Save both analysis and domain feedback to session
        try:
            session_manager.add_history_feedback(
                student_id=student_id,
                analysis_result=analysis_result,
                domain_feedback=feedback_result
            )
            print(f"[{datetime.now()}] ✅ Successfully saved feedback results to session")
        except Exception as save_error:
            print(f"[{datetime.now()}] ⚠️ Failed to save feedback to session: {str(save_error)}")
            print(f"[{datetime.now()}] ⚠️ Error details: {type(save_error).__name__}")
        
        return {
            "case_id": case_id,
            "student_id": student_id,
            "timestamp": datetime.now().isoformat(),
            "feedback_result": feedback_result,
            "metadata": {
                "processing_time_seconds": (datetime.now() - start_time).total_seconds(),
                "model_version": "gpt-4-turbo",
                "source": "langchain",
                "debug_file": str(debug_file) if 'debug_file' in locals() else None
            }
        }
        
    except Exception as e:
        error_msg = f"Error in get_history_aetcom_feedback with LangChain: {str(e)}"
        print(f"[{datetime.now()}] ❌ {error_msg}")
        print(f"[{datetime.now()}] ❌ Error type: {type(e).__name__}")
        print(f"[{datetime.now()}] ❌ Error details: {str(e)}")
        import traceback
        print(f"[{datetime.now()}] ❌ Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=error_msg) 
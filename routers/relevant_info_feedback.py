from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List
from datetime import datetime
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
import os
from dotenv import load_dotenv
import json
from utils.text_cleaner import clean_code_block
import google.generativeai as genai
import asyncio

# Load environment variables
load_dotenv()

findings_router = APIRouter()

# Initialize the OpenAI model
model = ChatOpenAI(
    model_name="gpt-4o",
    temperature=0.3,
    api_key=os.getenv("OPENAI_API_KEY"),
    timeout=100
)

# Initialize the Gemini model
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

class StudentFindings(BaseModel):
    case_id: str
    findings: List[str]

class EvaluationResponse(BaseModel):
    feedback: dict
    timestamp: str
    case_id: str
    metadata: dict = None

def get_critical_findings(case_id: str) -> str:
    """Get the critical findings from the relevant points markdown file"""
    try:
        findings_path = f"case-data/case{case_id}/clinical_findings_context.md"
        with open(findings_path, 'r') as file:
            return file.read()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Critical findings not found for case ID: {case_id}")

@findings_router.post("/evaluate-findings", response_model=EvaluationResponse)
async def evaluate_findings(request: StudentFindings):
    try:
        critical_findings = get_critical_findings(request.case_id)
        formatted_findings = "\n".join(f"- {item}" for item in request.findings)
        if(len(request.findings) == 0):
            formatted_findings = "No findings submitted by the student"
        prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                """You are a clinical reasoning tutor in a medical education tool.

The student is learning how to identify relevant findings from history and physical exam. Some of their answers may be vague or loosely worded — this is expected. Accept partial matches generously if they suggest awareness of the concept.

You are given:
- A list of **critical findings** expected for the case.
- A list of **findings submitted by the student**.

Your task:
1. Compare the student's findings with the expected list.
2. Accept partial matches (e.g., "tired" matches "general fatigue").
3. Identify any expected findings that the student **completely missed** or **hinted at too weakly**.
4. For each missed finding, return a:
   - `finding`: the exact expected finding.
   - `reason`: 1 sentence about why it's important — speak to the student directly, in a warm and helpful tone.
   - `question`: an **indirect, Socratic-style question** that nudges the student to think.  
     • Avoid direct phrasing like "Did the patient…"  
     • Instead, ask things like:  
       - "What might the skin look like after the rash fades?"  
       - "Could their energy levels tell you something deeper?"  
       - "Is there anything in their family background that could shape your thinking?"

These are the critical findings expected:
{critical_findings}

Student submitted:
{student_findings}

Return a JSON object in this format:
{{
  "message": "<encouraging overall message>",
  "missing_findings": [
    {{
      "finding": "<exact expected finding>",
      "reason": "<why it matters – addressed to the student>",
      "question": "<indirect Socratic-style prompt>"
    }}
  ]
}}

Only output the JSON. No extra explanations."""
            ),
            (
                "human",
                "Evaluate and return JSON feedback."
            )
        ])

        response = model.invoke(prompt.invoke({
            "critical_findings": critical_findings,
            "student_findings": formatted_findings
        }))

        cleaned = clean_code_block(response.content)
        parsed = json.loads(cleaned)

        return EvaluationResponse(
            feedback=parsed,
            timestamp=datetime.now().isoformat(),
            case_id=request.case_id
        )

    except json.JSONDecodeError:
        print(f"JSON Parse Error: {response.content}")  # Debug log
        raise HTTPException(status_code=500, detail="Failed to parse AI response as JSON")
    except Exception as e:
        error_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{error_timestamp}] ❌ Error in evaluate_findings: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

def load_prompt(file_path: str) -> str:
    """Load the prompt from a specified file."""
    try:
        with open(file_path, 'r') as file:
            return file.read()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Prompt file not found: {file_path}")

# Load the prompts from files
FINDINGS_EVALUATION_PROMPT = load_prompt("prompts/relevant_info_feedback.txt")
SINGLE_FINDING_EVALUATION_PROMPT = load_prompt("prompts/relevant_info_single_feedback.txt")

@findings_router.post("/evaluate-findings-gemini", response_model=EvaluationResponse)
async def evaluate_findings_gemini(request: StudentFindings):
    try:
        critical_findings = get_critical_findings(request.case_id)
        formatted_findings = "\n".join(f"- {item}" for item in request.findings)
        if(len(request.findings) == 0):
            formatted_findings = "No findings submitted by the student"
        
        # Format the prompt with the specific inputs
        formatted_prompt = FINDINGS_EVALUATION_PROMPT.format(
            critical_findings=critical_findings,
            student_findings=formatted_findings
        )
        
        # Configure the model
        model = genai.GenerativeModel('gemini-2.0-flash')
        generation_config = {
            "temperature": 0.3,
            "top_p": 0.95,
            "top_k": 40
        }
        
        # Prepare the content for generation
        content = {
            "contents": [{"parts": [{"text": formatted_prompt}]}],
            "generation_config": generation_config
        }
        
        print(f"[{datetime.now()}] 🔍 Generating findings feedback with Gemini for case {request.case_id}")
        start_time = datetime.now()
        
        # Generate the response
        response = await asyncio.to_thread(model.generate_content, **content)
        response_content = response.text
        
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        
        # Clean and parse the response
        cleaned = clean_code_block(response_content)
        parsed = json.loads(cleaned)
        
        response_data = {
            "feedback": parsed,
            "timestamp": datetime.now().isoformat(),
            "case_id": request.case_id,
            "metadata": {
                "processing_time_seconds": processing_time,
                "model_version": model.model_name,
                "generation_config": generation_config
            }
        }
        
        return response_data

    except json.JSONDecodeError as e:
        print(f"[{datetime.now()}] ❌ JSON parsing error: {str(e)}")
        print(f"[DEBUG] Failed JSON content: {response_content}")
        raise HTTPException(status_code=400, detail=f"Invalid response format: {str(e)}")
    except Exception as e:
        error_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{error_timestamp}] ❌ Error in evaluate_findings_gemini: {str(e)}")
        print(f"[DEBUG] Error type: {type(e).__name__}")
        print(f"[DEBUG] Full error details: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@findings_router.post("/evaluate-single-finding")
async def evaluate_single_finding(request: dict):
    """
    Evaluate a single finding against the critical findings for a case.
    Returns an encouraging message and whether the finding matches any critical findings.
    
    Request format:
    {
        "case_id": "1",
        "finding": "Patient has fever"
    }
    """
    try:
        print(f"[{datetime.now()}] 🔍 Evaluating single finding for case {request.get('case_id')}")
        print(f"[DEBUG] Finding to evaluate: {request.get('finding')}")
        
        if not request.get('case_id') or not request.get('finding'):
            print(f"[{datetime.now()}] ❌ Missing required fields in request")
            raise HTTPException(status_code=400, detail="Missing required fields: case_id and finding")
        
        start_time = datetime.now()
        
        # Get critical findings for the case
        critical_findings = get_critical_findings(request.get('case_id'))
        print(f"[DEBUG] Retrieved critical findings, length: {len(critical_findings)}")
        
        # Configure the model
        model = genai.GenerativeModel('gemini-2.0-flash')
        generation_config = {
            "temperature": 0.3,
            "top_p": 0.95,
            "top_k": 40
        }
        
        # Format the prompt with the specific inputs
        formatted_prompt = SINGLE_FINDING_EVALUATION_PROMPT.format(
            critical_findings=critical_findings,
            student_finding=request.get('finding')
        )
        
        # Prepare the content for generation
        content = {
            "contents": [{"parts": [{"text": formatted_prompt}]}],
            "generation_config": generation_config
        }
        
        # Generate the response
        print(f"[DEBUG] Sending prompt to Gemini model")
        response = await asyncio.to_thread(model.generate_content, **content)
        response_content = response.text
        print(f"[DEBUG] Received response from Gemini model")
        
        # Clean and parse the response
        cleaned = clean_code_block(response_content)
        parsed = json.loads(cleaned)
        print(f"[DEBUG] Parsed response: {json.dumps(parsed, indent=2)}")
        
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        
        response_data = {
            "finding": request.get('finding'),
            "evaluation": parsed,
            "timestamp": datetime.now().isoformat(),
            "case_id": request.get('case_id'),
            "metadata": {
                "processing_time_seconds": processing_time,
                "model_version": model.model_name,
                "generation_config": generation_config
            }
        }
        
        print(f"[{datetime.now()}] ✅ Successfully evaluated single finding in {processing_time:.2f} seconds")
        return response_data

    except json.JSONDecodeError as e:
        print(f"[{datetime.now()}] ❌ JSON parsing error: {str(e)}")
        print(f"[DEBUG] Failed JSON content: {response_content}")
        raise HTTPException(status_code=400, detail=f"Invalid response format: {str(e)}")
    except Exception as e:
        error_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{error_timestamp}] ❌ Error in evaluate_single_finding: {str(e)}")
        print(f"[DEBUG] Error type: {type(e).__name__}")
        print(f"[DEBUG] Full error details: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
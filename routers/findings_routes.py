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

# Load environment variables
load_dotenv()

findings_router = APIRouter()

# Initialize the model
model = ChatOpenAI(
    model_name="gpt-4o",
    temperature=0.3,
    api_key=os.getenv("OPENAI_API_KEY"),
    timeout=100
)

class StudentFindings(BaseModel):
    case_id: str
    findings: List[str]

class EvaluationResponse(BaseModel):
    feedback: dict
    timestamp: str
    case_id: str

def get_critical_findings(case_id: str) -> str:
    """Get the critical findings from the relevant points markdown file"""
    try:
        findings_path = f"case-data/case{case_id}/relevant-points.txt"
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
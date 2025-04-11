from fastapi import APIRouter, HTTPException
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from datetime import datetime
import os
from dotenv import load_dotenv
from typing import List
from pydantic import BaseModel
import json
from utils.text_cleaner import clean_code_block

# Load environment variables
load_dotenv()

router = APIRouter(
    prefix="/student-evaluation",
    tags=["evaluate-history"]
)

# Initialize the model
model = ChatOpenAI(
    model_name="gpt-4o-mini",
    temperature=0.7,
    api_key=os.getenv("OPENAI_API_KEY")
)

class StudentQuestionsRequest(BaseModel):
    case_id: str
    questions: List[str]

class EvaluationResponse(BaseModel):
    feedback: dict
    timestamp: str
    case_id: str

def get_case_document(case_id: str) -> str:
    """Retrieve the case document from the case folder."""
    try:
        case_doc_path = f"case-data/case{case_id}/history_question.txt"
        with open(case_doc_path, 'r') as file:
            return file.read()
    except FileNotFoundError:
        raise HTTPException(
            status_code=404, 
            detail=f"Case document not found for case ID: {case_id}"
        )

@router.post("/evaluate-questions", response_model=EvaluationResponse)
async def evaluate_student_questions(request: StudentQuestionsRequest):
    """Evaluate the student's history-taking questions."""
    try:
        # Get the case document
        case_document = get_case_document(request.case_id)
        
        # Format the questions as a numbered list
        formatted_questions = "\n".join(
            f"{i+1}. {q}" for i, q in enumerate(request.questions)
        )

        # Create the evaluation prompt
        evaluation_prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                """You are a clinical reasoning tutor reviewing a student's history-taking.

Your tasks:
1. From the case document below, identify only the questions explicitly labeled (or clearly marked) as "Important Questions".
2. Compare that list of important questions to the questions asked by the student.
   - A student's question counts as matched if it is essentially the same question, ignoring minor wording differences.
3. Create a comparative analysis showing:
   - Each of the top 3 important questions
   - Whether each was asked by the student (✓) or missed (✗)
   - Brief justification for the match/mismatch
4. Return a JSON response with the following structure (and no extra keys or fields):

{{
    "feedback": {{
        "message": "<appropriate message based on how many were missed>",
        "missed_count": <number>,
        "comparative_analysis": [
            {{
                "important_question": "<exact question from case>",
                "status": "<✓ or ✗>",
                "student_match": "<matching student question or 'Not Asked'>",
                "justification": "<why this is/isn't a match>"
            }}
        ],
        "missed_questions": [
            {{
                "question": "<the exact missed question>",
                "rationale": "<why this question is high-yield (avoid diagnostic hints)>"
            }}
        ]
    }}
}}

Message templates for "message":
- If missed 0: "🌟 Stellar performance! You've asked all the key questions. Keep going!"
- If missed 1: "You're just one question away from a complete history. Take a moment to revisit the case and see if anything subtle was missed."
- If missed 2+: "You've missed {{missed_count}} important questions that could impact your understanding of the case. Pause before moving ahead and think about what else might be relevant."

⚠️ Do not hint at or reveal the diagnosis in your response.
⚠️ Avoid describing how to reach or confirm a diagnosis—stick to the importance of the missed question itself.
✅ Your final output must be valid JSON following the exact structure above."""
            ),
            (
                "human",
                "Case Document:\n{case_document}\n\nStudent Questions:\n{student_questions}\n\nPlease evaluate the student's history-taking as instructed."
            )
        ])

        # Get the evaluation response
        response = model.invoke(evaluation_prompt.invoke({
            "case_document": case_document,
            "student_questions": formatted_questions
        }))

        # Clean the response content
        cleaned_content = clean_code_block(response.content)
        
        # Parse the cleaned JSON response
        response_content = json.loads(cleaned_content)
        
        return EvaluationResponse(
            feedback=response_content["feedback"],
            timestamp=datetime.now().isoformat(),
            case_id=request.case_id
        )

    except json.JSONDecodeError as e:
        print(f"JSON Parse Error: {response.content}")  # Debug log
        raise HTTPException(
            status_code=500,
            detail="Failed to parse AI response as JSON"
        )
    except Exception as e:
        error_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{error_timestamp}] ❌ Error in evaluate_student_questions: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) 
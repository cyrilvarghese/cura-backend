import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
from utils.text_cleaner import clean_code_block

feedback_router = APIRouter(
    prefix="/get-feedback",
    tags=["feedback"]
)

class StudentMessage(BaseModel):
    content: str
    step: str
    timestamp: datetime
    type: Optional[str] = Field(
        None,
        description="Message type",
        pattern='^(text|image|test-result|examination|diagnosis|relevant-info|final-diagnosis|feedback)$'
    )

# Define the Annotation model
class Annotation(BaseModel):
    action: str
    step: str
    relevance: Optional[str] = None
    correctness: Optional[str] = None
    justification: str

# Define the FeedbackCategory model
class FeedbackCategory(BaseModel):
    score: int
    comments: str

# Define the DetailedFeedback model
class DetailedFeedback(BaseModel):
    history_taking: FeedbackCategory
    examinations_performed: FeedbackCategory
    tests_ordered: FeedbackCategory
    diagnostic_reasoning: FeedbackCategory
    synthesis_organization: FeedbackCategory

# Update the FeedbackResponse model
class FeedbackResponse(BaseModel):
    annotations: List[Annotation]
    feedback: DetailedFeedback
    total_score: float
    suggestions: str

class FeedbackRequest(List[StudentMessage]):
    pass

# Initialize the LLM
llm = ChatOpenAI(
    model_name="gpt-4o-mini",
    temperature=0
)

async def get_case_summary(case_id: str = None) -> str:
    try:
        case_id = case_id or "case1"  # Default to case1 if no ID provided
        file_path = f"case-data/case{case_id}/case_doc.txt"
        
        with open(file_path, 'r') as file:
            return file.read().strip()
            
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Case summary not found for case_id: {case_id}"
        )

def transform_student_actions(messages: List[StudentMessage]) -> str:
    # Use set to track unique content-step combinations
    seen = set()
    transformed_actions = []
    
    for i, message in enumerate(messages, 1):
        # Create unique key from content and step
        unique_key = (message.content, message.step)
        
        # Only add if we haven't seen this combination before
        if unique_key not in seen:
            action = f"{i}. \"{message.content}\" ({message.step})"
            transformed_actions.append(action)
            seen.add(unique_key)
    
    return "\n".join(transformed_actions)

def load_prompt_template(file_path: str) -> str:
    with open(file_path, 'r') as file:
        return file.read()

 

@feedback_router.post("/", response_model=FeedbackResponse)
async def submit_feedback(messages: List[StudentMessage], case_id: str = None):
    try:
         # Log the received data
        print("\nReceived Student Actions:")
        for action in messages:
            print(f"Step: {action.step}")
            print(f"Time: {action.timestamp}")
            print(f"Content: {action.content}")
            print("---")

        case_summary = await get_case_summary(case_id)
        
        # Create the prompt template
        template = load_prompt_template('prompts/medical_evaluator.txt')
            
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", template),
            ("human", "Here are the student's actions:\n{student_actions}")
        ])
        
        # Invoke the prompt template with variables
        formatted_prompt = prompt_template.invoke({
            "case_summary": case_summary,
            "student_actions": transform_student_actions(messages)
        })
        
        # Send to LLM and get response
        llm_response = llm.invoke(formatted_prompt)
        cleaned_response = clean_code_block(llm_response.content)
        parsed_response = json.loads(cleaned_response)
        # Parse the LLM response and convert to FeedbackResponse
        return FeedbackResponse(
            annotations=parsed_response['annotations'],
            feedback=parsed_response['feedback'],
            total_score=parsed_response['total_score'],
            suggestions=parsed_response['suggestions']
        )
    except Exception as e:
        print(f"Error occurred: {e}")  # Print the error message
        raise HTTPException(status_code=500, detail=str(e)) 
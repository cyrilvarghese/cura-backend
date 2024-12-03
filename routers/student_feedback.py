from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

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

class FeedbackResponse(BaseModel):
    score: float
    correctDiagnosis: str
    feedback: str
    explanations: List[str]
    recommendations: List[str]

class FeedbackRequest(List[StudentMessage]):
    pass




@feedback_router.post("/", response_model=FeedbackResponse)
async def submit_feedback(messages: List[StudentMessage]):
    try:
        # Log the received data
        print("\nReceived Student Actions:")
        for action in messages:
            print(f"Step: {action.step}")
            print(f"Time: {action.timestamp}")
            print(f"Content: {action.content}")
            print("---")

        # Return using existing FeedbackResponse model
        return FeedbackResponse(
            score=100,
            correctDiagnosis="Urticarial vasculitis",
            feedback="Data logged successfully",
            explanations=["Actions have been logged"],
            recommendations=["No recommendations at this time"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 
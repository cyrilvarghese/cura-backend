from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from utils.session_manager import SessionManager
from auth.auth_api import get_user
from datetime import datetime

router = APIRouter()

class OSCEScoreDetails(BaseModel):
    overallPercentage: float
    totalPointsEarned: float
    totalPossiblePoints: float

class QuestionTypePerformance(BaseModel):
    imageBasedPercentage: float
    multipleChoicePercentage: float
    writtenResponsePercentage: float

class OSCEScoreSubmission(BaseModel):
    case_id: str
    overallPerformance: OSCEScoreDetails
    performanceByQuestionType: QuestionTypePerformance

@router.post("/record-osce-score")
async def record_osce_score(
    request: OSCEScoreSubmission,
    session_manager: SessionManager = Depends(lambda: SessionManager())
):
    """
    Record the student's OSCE score including overall performance and performance by question type.
    """
    # First handle authentication outside main try block
    try:
        user_response = await get_user()
        if not user_response["success"]:
            error_message = user_response.get("error", "Authentication required")
            raise HTTPException(status_code=401, detail=error_message)
        
        student_id = user_response["user"]["id"]
    except HTTPException as auth_error:
        raise auth_error
    except Exception as auth_error:
        raise HTTPException(status_code=401, detail="Authentication failed")

    try:
        # Create OSCE score data structure
        osce_score_data = {
            "overallPerformance": {
                "overallPercentage": request.overallPerformance.overallPercentage,
                "totalPointsEarned": request.overallPerformance.totalPointsEarned,
                "totalPossiblePoints": request.overallPerformance.totalPossiblePoints
            },
            "performanceByQuestionType": {
                "imageBasedPercentage": request.performanceByQuestionType.imageBasedPercentage,
                "multipleChoicePercentage": request.performanceByQuestionType.multipleChoicePercentage,
                "writtenResponsePercentage": request.performanceByQuestionType.writtenResponsePercentage
            },
            "timestamp": datetime.now().isoformat()
        }
        
        # Add to session using the specialized method
        session_data = session_manager.add_osce_score(
            student_id=student_id,
            case_id=request.case_id,
            osce_score_data=osce_score_data
        )
        
        print(f"Recorded OSCE score for student {student_id} in case {request.case_id}")
        
        return {
            "status": "success",
            "message": "OSCE score recorded successfully",
            "session_data": session_data
        }
        
    except HTTPException as http_error:
        raise http_error
    except Exception as e:
        print(f"Unexpected error in record_osce_score: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred while recording OSCE score: {str(e)}"
        ) 
from fastapi import APIRouter, HTTPException, Depends
from typing import List
from pydantic import BaseModel
from utils.session_manager import SessionManager
from auth.auth_api import get_user
from datetime import datetime

router = APIRouter()

class TreatmentPlanSubmission(BaseModel):
    case_id: str
    treatment_plan: List[str]

@router.post("/treatment-plan")
async def submit_treatment_plan(
    request: TreatmentPlanSubmission,
    session_manager: SessionManager = Depends(lambda: SessionManager())
):
    """
    Record the student's treatment plan.
    """
    # Handle authentication
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
        # Add to session
        session_data = session_manager.add_treatment_plan(
            student_id=student_id,
            case_id=request.case_id,
            treatment_plan=request.treatment_plan
        )
        
        print(f"Recorded treatment plan for student {student_id} in case {request.case_id}")
        
        return {
            "status": "success",
            "message": "Treatment plan recorded successfully",
            "session_data": session_data
        }
        
    except HTTPException as http_error:
        raise http_error
    except Exception as e:
        print(f"Unexpected error in submit_treatment_plan: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while recording treatment plan"
        ) 
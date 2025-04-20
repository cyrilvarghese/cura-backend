from fastapi import APIRouter, HTTPException, Depends
from typing import List
from pydantic import BaseModel
from utils.session_manager import SessionManager
from auth.auth_api import get_user
from datetime import datetime

router = APIRouter()

class TreatmentMonitoringSubmission(BaseModel):
    case_id: str
    pre_treatment_checks: List[str]
    post_treatment_monitoring: List[str]

@router.post("/treatment-monitoring")
async def submit_treatment_monitoring(
    request: TreatmentMonitoringSubmission,
    session_manager: SessionManager = Depends(lambda: SessionManager())
):
    """
    Record the student's pre-treatment checks and post-treatment monitoring plan.
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
        session_data = session_manager.add_treatment_monitoring_data(
            student_id=student_id,
            case_id=request.case_id,
            pre_treatment_checks=request.pre_treatment_checks,
            post_treatment_monitoring=request.post_treatment_monitoring
        )
        
        print(f"Recorded treatment monitoring data for student {student_id} in case {request.case_id}")
        
        return {
            "status": "success",
            "message": "Treatment monitoring data recorded successfully",
            "session_data": session_data
        }
        
    except HTTPException as http_error:
        raise http_error
    except Exception as e:
        print(f"Unexpected error in submit_treatment_monitoring: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while recording treatment monitoring data"
        ) 
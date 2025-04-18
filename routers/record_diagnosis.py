from fastapi import APIRouter, HTTPException, Depends
from typing import List
from pydantic import BaseModel
from utils.session_manager import SessionManager
from auth.auth_api import get_user
from datetime import datetime

router = APIRouter()

class DiagnosisSubmission(BaseModel):
    case_id: str
    primary_diagnosis: str
    reason: str
    differentials: List[str]  # Simple array of strings

@router.post("/record-diagnosis")
async def record_diagnosis(
    request: DiagnosisSubmission,
    session_manager: SessionManager = Depends(lambda: SessionManager())
):
    """
    Record the student's diagnosis submission including primary diagnosis and differentials.
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
        # Create diagnosis submission data structure
        diagnosis_data = {
            "primary_diagnosis": request.primary_diagnosis,
            "reason": request.reason,
            "differentials": request.differentials,  # Now just an array of strings
            "timestamp": datetime.now().isoformat()
        }
        
        # Add to session
        session_data = session_manager.add_diagnosis_submission(
            student_id=student_id,
            case_id=request.case_id,
            diagnosis_data=diagnosis_data
        )
        
        print(f"Recorded diagnosis for student {student_id} in case {request.case_id}")
        
        return {
            "status": "success",
            "message": "Diagnosis recorded successfully",
            "session_data": session_data
        }
        
    except HTTPException as http_error:
        raise http_error
    except Exception as e:
        print(f"Unexpected error in record_diagnosis: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while recording diagnosis"
        ) 
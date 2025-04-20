from fastapi import APIRouter, HTTPException, Depends
from typing import List
from pydantic import BaseModel
from utils.session_manager import SessionManager
from auth.auth_api import get_user
from datetime import datetime

router = APIRouter()

class FinalDiagnosisSubmission(BaseModel):
    case_id: str
    final_diagnosis: str
    final_reason: str

@router.post("/final-diagnosis")
async def submit_final_diagnosis(
    request: FinalDiagnosisSubmission,
    session_manager: SessionManager = Depends(lambda: SessionManager())
):
    """
    Record the student's final diagnosis submission including the final diagnosis and reasoning.
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
        # Create final diagnosis data structure
        final_diagnosis_data = {
            "final_diagnosis": request.final_diagnosis,
            "final_reason": request.final_reason,
            "timestamp": datetime.now().isoformat()
        }
        
        # Add to session
        session_data = session_manager.add_final_diagnosis(
            student_id=student_id,
            case_id=request.case_id,
            final_diagnosis_data=final_diagnosis_data
        )
        
        print(f"Recorded final diagnosis for student {student_id} in case {request.case_id}")
        
        return {
            "status": "success",
            "message": "Final diagnosis recorded successfully",
            "session_data": session_data
        }
        
    except HTTPException as http_error:
        raise http_error
    except Exception as e:
        print(f"Unexpected error in submit_final_diagnosis: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while recording final diagnosis"
        ) 
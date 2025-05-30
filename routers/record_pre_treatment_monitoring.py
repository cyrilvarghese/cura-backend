from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, List
from pydantic import BaseModel
from utils.session_manager import SessionManager
from auth.auth_api import get_user_from_token
from datetime import datetime

# Define the security scheme
security = HTTPBearer()

router = APIRouter(
    prefix="/pre-treatment-monitoring",
    tags=["pre-treatment-monitoring"]
)

class TreatmentMonitoringSubmission(BaseModel):
    case_id: str
    pre_treatment_checks: List[str]
    post_treatment_monitoring: List[str]

@router.post("/record")
async def record_pre_treatment_monitoring(
    monitoring_data: dict,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Record pre-treatment monitoring data for a case.
    """
    print(f"[PRE_TREATMENT_MONITORING] 📝 Recording monitoring data: {monitoring_data}")
    
    # Extract token and authenticate the user
    try:
        token = credentials.credentials
        print(f"[DEBUG] Extracted JWT: {token}")
        
        print(f"[PRE_TREATMENT_MONITORING] 🔐 Authenticating user...")
        user_response = await get_user_from_token(token)
        if not user_response["success"]:
            error_message = user_response.get("error", "Authentication required")
            print(f"[PRE_TREATMENT_MONITORING] ❌ Authentication failed: {error_message}")
            raise HTTPException(status_code=401, detail=error_message)
        
        user_id = user_response["user"]["id"]
        print(f"[PRE_TREATMENT_MONITORING] ✅ User authenticated successfully. User ID: {user_id}")
        
        try:
            session_manager = SessionManager()
            session_data = session_manager.add_pre_treatment_monitoring(
                student_id=user_id,
                case_id=monitoring_data["case_id"],
                monitoring_data=monitoring_data["monitoring_data"]
            )
            
            print(f"Recorded pre-treatment monitoring for student {user_id} in case {monitoring_data['case_id']}")
            
            return {
                "status": "success",
                "message": "Pre-treatment monitoring recorded successfully",
                "session_data": session_data
            }
        except Exception as e:
            print(f"[PRE_TREATMENT_MONITORING] ❌ Error recording monitoring data: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error recording pre-treatment monitoring: {str(e)}")
            
    except HTTPException as auth_error:
        print(f"[PRE_TREATMENT_MONITORING] ❌ HTTP exception during authentication: {str(auth_error)}")
        raise auth_error
    except Exception as auth_error:
        print(f"[PRE_TREATMENT_MONITORING] ❌ Unexpected error during authentication: {str(auth_error)}")
        raise HTTPException(status_code=401, detail="Authentication failed")

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
        user_response = await get_user_from_token()
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
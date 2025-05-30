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
    prefix="/treatment-plan",
    tags=["treatment-plan"]
)

class TreatmentPlanSubmission(BaseModel):
    case_id: str
    treatment_plan: List[str]

@router.post("/record")
async def record_treatment_plan(
    treatment_data: dict,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Record a treatment plan for a case.
    """
    print(f"[TREATMENT_PLAN] 📝 Recording treatment plan with data: {treatment_data}")
    
    # Extract token and authenticate the user
    try:
        token = credentials.credentials
        print(f"[DEBUG] Extracted JWT: {token}")
        
        print(f"[TREATMENT_PLAN] 🔐 Authenticating user...")
        user_response = await get_user_from_token(token)
        if not user_response["success"]:
            error_message = user_response.get("error", "Authentication required")
            print(f"[TREATMENT_PLAN] ❌ Authentication failed: {error_message}")
            raise HTTPException(status_code=401, detail=error_message)
        
        user_id = user_response["user"]["id"]
        print(f"[TREATMENT_PLAN] ✅ User authenticated successfully. User ID: {user_id}")
        
        try:
            session_manager = SessionManager()
            session_data = session_manager.add_treatment_plan(
                student_id=user_id,
                case_id=treatment_data["case_id"],
                treatment_plan=treatment_data["treatment_plan"]
            )
            
            print(f"Recorded treatment plan for student {user_id} in case {treatment_data['case_id']}")
            
            return {
                "status": "success",
                "message": "Treatment plan recorded successfully",
                "session_data": session_data
            }
        except Exception as e:
            print(f"[TREATMENT_PLAN] ❌ Error recording treatment plan: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error recording treatment plan: {str(e)}")
            
    except HTTPException as auth_error:
        print(f"[TREATMENT_PLAN] ❌ HTTP exception during authentication: {str(auth_error)}")
        raise auth_error
    except Exception as auth_error:
        print(f"[TREATMENT_PLAN] ❌ Unexpected error during authentication: {str(auth_error)}")
        raise HTTPException(status_code=401, detail="Authentication failed") 
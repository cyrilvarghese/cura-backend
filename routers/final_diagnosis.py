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
    prefix="/final-diagnosis",
    tags=["final-diagnosis"]
)

class FinalDiagnosisSubmission(BaseModel):
    case_id: str
    final_diagnosis: str
    final_reason: str

@router.post("/record")
async def record_final_diagnosis(
    diagnosis_data: dict,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Record final diagnosis for a case.
    """
    print(f"[FINAL_DIAGNOSIS] 📝 Recording final diagnosis with data: {diagnosis_data}")
    
    # Extract token and authenticate the user
    try:
        token = credentials.credentials
        print(f"[DEBUG] Extracted JWT: {token}")
        
        print(f"[FINAL_DIAGNOSIS] 🔐 Authenticating user...")
        user_response = await get_user_from_token(token)
        if not user_response["success"]:
            error_message = user_response.get("error", "Authentication required")
            print(f"[FINAL_DIAGNOSIS] ❌ Authentication failed: {error_message}")
            raise HTTPException(status_code=401, detail=error_message)
        
        user_id = user_response["user"]["id"]
        print(f"[FINAL_DIAGNOSIS] ✅ User authenticated successfully. User ID: {user_id}")
        
        try:
            session_manager = SessionManager()
            session_data = session_manager.add_final_diagnosis(
                student_id=user_id,
                case_id=diagnosis_data["case_id"],
                final_diagnosis_data=diagnosis_data
            )
            
            print(f"Recorded final diagnosis for student {user_id} in case {diagnosis_data['case_id']}")
            
            return {
                "status": "success",
                "message": "Final diagnosis recorded successfully",
                "session_data": session_data
            }
        except Exception as e:
            print(f"[FINAL_DIAGNOSIS] ❌ Error recording final diagnosis: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error recording final diagnosis: {str(e)}")
            
    except HTTPException as auth_error:
        print(f"[FINAL_DIAGNOSIS] ❌ HTTP exception during authentication: {str(auth_error)}")
        raise auth_error
    except Exception as auth_error:
        print(f"[FINAL_DIAGNOSIS] ❌ Unexpected error during authentication: {str(auth_error)}")
        raise HTTPException(status_code=401, detail="Authentication failed") 
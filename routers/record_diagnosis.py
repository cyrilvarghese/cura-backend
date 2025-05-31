from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import List
from pydantic import BaseModel
from utils.session_manager import SessionManager
from auth.auth_api import get_user, get_user_from_token
from datetime import datetime
import json

# Define the security scheme
security = HTTPBearer()

router = APIRouter(
    prefix="/diagnosis",
    tags=["diagnosis"]
)

class DiagnosisSubmission(BaseModel):
    case_id: str
    primary_diagnosis: str
    incorrect_differentials: List[str]
    reason: str
    differentials: List[str]  # Simple array of strings

@router.post("/record")
async def record_diagnosis(
    diagnosis_data: dict,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Record a diagnosis for a case.
    """
    print(f"[DIAGNOSIS] 📝 Recording diagnosis with data: {diagnosis_data}")
    
    # Extract token and authenticate the user
    try:
        token = credentials.credentials
        print(f"[DEBUG] Extracted JWT: {token}")
        
        print(f"[DIAGNOSIS] 🔐 Authenticating user...")
        user_response = await get_user_from_token(token)
        if not user_response["success"]:
            error_message = user_response.get("error", "Authentication required")
            print(f"[DIAGNOSIS] ❌ Authentication failed: {error_message}")
            raise HTTPException(status_code=401, detail=error_message)
        
        user_id = user_response["user"]["id"]
        print(f"[DIAGNOSIS] ✅ User authenticated successfully. User ID: {user_id}")
        
        try:
            # Create diagnosis submission data structure
            diagnosis_data = {
                "primary_diagnosis": diagnosis_data["primary_diagnosis"],
                "reason": diagnosis_data["reason"],
                "differentials": diagnosis_data["differentials"], 
                "incorrect_differentials": diagnosis_data["incorrect_differentials"], # Now just an array of strings
                "timestamp": datetime.now().isoformat(),
                "case_id": diagnosis_data["case_id"]
            }
            
            # Add to session
            session_manager = SessionManager()
            session_data = session_manager.add_diagnosis_submission(
                student_id=user_id,
                case_id=diagnosis_data["case_id"],
                diagnosis_data=diagnosis_data
            )
            
            print(f"Recorded diagnosis for student {user_id} in case {diagnosis_data['case_id']}")
            
            return {
                "status": "success",
                "message": "Diagnosis recorded successfully",
                "session_data": session_data
            }
        except Exception as e:
            print(f"[DIAGNOSIS] ❌ Error recording diagnosis: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error recording diagnosis: {str(e)}")
            
    except HTTPException as auth_error:
        print(f"[DIAGNOSIS] ❌ HTTP exception during authentication: {str(auth_error)}")
        raise auth_error
    except Exception as auth_error:
        print(f"[DIAGNOSIS] ❌ Unexpected error during authentication: {str(auth_error)}")
        raise HTTPException(status_code=401, detail="Authentication failed") 
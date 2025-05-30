from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, List
from datetime import datetime
import json
from utils.session_manager import SessionManager
from auth.auth_api import get_user_from_token
from pydantic import BaseModel
# Define the security scheme
security = HTTPBearer()

router = APIRouter(
    prefix="/clinical-findings",
    tags=["clinical-findings"]
)

class ClinicalFindingsRequest(BaseModel):
    findings: List[str]
    case_id: str

@router.post("/record")
async def record_clinical_findings(
    findings_data: dict,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Record clinical findings for a case.
    """
    print(f"[CLINICAL_FINDINGS] 📝 Recording clinical findings with data: {findings_data}")
    
    # Extract token and authenticate the user
    try:
        token = credentials.credentials
        print(f"[DEBUG] Extracted JWT: {token}")
        
        print(f"[CLINICAL_FINDINGS] 🔐 Authenticating user...")
        user_response = await get_user_from_token(token)
        if not user_response["success"]:
            error_message = user_response.get("error", "Authentication required")
            print(f"[CLINICAL_FINDINGS] ❌ Authentication failed: {error_message}")
            raise HTTPException(status_code=401, detail=error_message)
        
        user_id = user_response["user"]["id"]
        print(f"[CLINICAL_FINDINGS] ✅ User authenticated successfully. User ID: {user_id}")
        
        try:
            session_manager = SessionManager()
            session_data = None
            
            # Add each finding to the session
            for finding in findings_data["findings"]:
                session_data = session_manager.add_clinical_finding(
                    student_id=user_id,
                    case_id=findings_data["case_id"],
                    finding=finding
                )
            
            print(f"Recorded {len(findings_data['findings'])} clinical findings for student {user_id} in case {findings_data['case_id']}")
            
            return {
                "status": "success",
                "message": f"Recorded {len(findings_data['findings'])} clinical findings",
                "session_data": session_data
            }
        except Exception as e:
            print(f"[CLINICAL_FINDINGS] ❌ Error recording clinical findings: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error recording clinical findings: {str(e)}")
            
    except HTTPException as auth_error:
        print(f"[CLINICAL_FINDINGS] ❌ HTTP exception during authentication: {str(auth_error)}")
        raise auth_error
    except Exception as auth_error:
        print(f"[CLINICAL_FINDINGS] ❌ Unexpected error during authentication: {str(auth_error)}")
        raise HTTPException(status_code=401, detail="Authentication failed") 
from fastapi import APIRouter, HTTPException, Depends
from typing import List
from pydantic import BaseModel
from utils.session_manager import SessionManager
from auth.auth_api import get_user

router = APIRouter()

class ClinicalFindingsRequest(BaseModel):
    findings: List[str]
    case_id: str

@router.post("/record-clinical-findings")
async def record_clinical_findings(
    request: ClinicalFindingsRequest,
    session_manager: SessionManager = Depends(lambda: SessionManager())
):
    """
    Record multiple clinical findings for a student's session.
    
    Args:
        request: Contains case_id and an array of clinical findings
    
    Returns:
        The updated session data
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
        session_data = None
        
        # Add each finding to the session
        for finding in request.findings:
            session_data = session_manager.add_clinical_finding(
                student_id=student_id,
                case_id=request.case_id,
                finding=finding
            )
        
        print(f"Recorded {len(request.findings)} clinical findings for student {student_id} in case {request.case_id}")
        
        return {
            "status": "success",
            "message": f"Recorded {len(request.findings)} clinical findings",
            "session_data": session_data
        }
        
    except HTTPException as http_error:
        raise http_error
    except Exception as e:
        print(f"Unexpected error in record_clinical_findings: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while recording clinical findings"
        ) 
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from utils.session_manager import SessionManager
from utils.supabase_session import submit_session_to_supabase
from auth.auth_api import get_user_from_token
from datetime import datetime
import json

# Define the security scheme
security = HTTPBearer()

router = APIRouter()

class OSCEScoreDetails(BaseModel):
    overallPercentage: float
    totalPointsEarned: float
    totalPossiblePoints: float

class QuestionTypePerformance(BaseModel):
    imageBasedPercentage: float
    multipleChoicePercentage: float
    writtenResponsePercentage: float

class OSCEScoreSubmission(BaseModel):
    case_id: str
    overallPerformance: OSCEScoreDetails
    performanceByQuestionType: QuestionTypePerformance
    department: str

@router.post("/record-osce-score")
async def record_osce_score(
    request: OSCEScoreSubmission,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    session_manager: SessionManager = Depends(lambda: SessionManager())
):
    """
    Record the student's OSCE score including overall performance and performance by question type.
    Then submit the complete session data to Supabase for analytics and reporting.
    """
    print(f"[OSCE_SCORE] 📝 Received request to record OSCE score for case: {request.case_id}")
    print(f"[OSCE_SCORE] Request payload: {json.dumps(request.dict(), indent=2)}")
    
    # First handle authentication outside main try block
    try:
        token = credentials.credentials
        print(f"[DEBUG] Extracted JWT: {token}")
        
        print(f"[OSCE_SCORE] 🔐 Authenticating user...")
        user_response = await get_user_from_token(token)
        if not user_response["success"]:
            error_message = user_response.get("error", "Authentication required")
            print(f"[OSCE_SCORE] ❌ Authentication failed: {error_message}")
            raise HTTPException(status_code=401, detail=error_message)
        
        student_id = user_response["user"]["id"]
        print(f"[OSCE_SCORE] ✅ User authenticated successfully. Student ID: {student_id}")
    except HTTPException as auth_error:
        print(f"[OSCE_SCORE] ❌ HTTP exception during authentication: {str(auth_error)}")
        raise auth_error
    except Exception as auth_error:
        print(f"[OSCE_SCORE] ❌ Unexpected error during authentication: {str(auth_error)}")
        raise HTTPException(status_code=401, detail="Authentication failed")

    try:
        print(f"[OSCE_SCORE] 📊 Creating OSCE score data structure...")
        # Create OSCE score data structure
        osce_score_data = {
            "overallPerformance": {
                "overallPercentage": request.overallPerformance.overallPercentage,
                "totalPointsEarned": request.overallPerformance.totalPointsEarned,
                "totalPossiblePoints": request.overallPerformance.totalPossiblePoints
            },
            "performanceByQuestionType": {
                "imageBasedPercentage": request.performanceByQuestionType.imageBasedPercentage,
                "multipleChoicePercentage": request.performanceByQuestionType.multipleChoicePercentage,
                "writtenResponsePercentage": request.performanceByQuestionType.writtenResponsePercentage
            },
            "timestamp": datetime.now().isoformat()
        }
        print(f"[OSCE_SCORE] OSCE score data: {json.dumps(osce_score_data, indent=2)}")
        
        print(f"[OSCE_SCORE] 💾 Adding OSCE score to session data using SessionManager...")
        # Add to session using the specialized method
        session_data = session_manager.add_osce_score(
            student_id=student_id,
            case_id=request.case_id,
            osce_score_data=osce_score_data
        )
        
        print(f"[OSCE_SCORE] ✅ Successfully recorded OSCE score for student {student_id} in case {request.case_id}")
        print(f"[OSCE_SCORE] Session keys after update: {', '.join(session_data.keys())}")
        print(f"[OSCE_SCORE] Interaction keys after update: {', '.join(session_data.get('interactions', {}).keys())}")
        
        # Submit the complete session data to Supabase
        print(f"[OSCE_SCORE] 🚀 Submitting session data to Supabase...")
        try:
            supabase_result = await submit_session_to_supabase(session_data, request.department)
            print(f"[OSCE_SCORE] ✅ Session data submitted to Supabase successfully!")
            print(f"[OSCE_SCORE] Supabase result: {json.dumps(supabase_result, indent=2)}")
        except Exception as supabase_error:
            # Log error but don't fail the API call if Supabase submission fails
            print(f"[OSCE_SCORE] ⚠️ WARNING: Failed to submit session to Supabase")
            print(f"[OSCE_SCORE] Error details: {str(supabase_error)}")
            print(f"[OSCE_SCORE] Error type: {type(supabase_error).__name__}")
        
        print(f"[OSCE_SCORE] 🏁 OSCE score recording completed successfully")
        return {
            "status": "success",
            "message": "OSCE score recorded successfully",
            "session_data": session_data
        }
        
    except HTTPException as http_error:
        print(f"[OSCE_SCORE] ❌ HTTP exception during OSCE score recording: {str(http_error)}")
        raise http_error
    except Exception as e:
        print(f"[OSCE_SCORE] ❌ Unexpected error in record_osce_score: {str(e)}")
        print(f"[OSCE_SCORE] Error type: {type(e).__name__}")
        if hasattr(e, '__traceback__'):
            import traceback
            tb_str = ''.join(traceback.format_tb(e.__traceback__))
            print(f"[OSCE_SCORE] Error traceback: \n{tb_str}")
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred while recording OSCE score: {str(e)}"
        )
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import json
import os
from pathlib import Path
from datetime import datetime
from auth.auth_api import get_user_from_token

# Define the security scheme
security = HTTPBearer()

router = APIRouter(
    prefix="/case-quote",
    tags=["case-quote"]
)

class UpdateCaseQuoteRequest(BaseModel):
    case_id: int
    quote: str

@router.post("/update")
async def update_case_quote(
    request: UpdateCaseQuoteRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Update the quote in a case's cover file"""
    print(f"[CASE_QUOTE] 📝 Updating case quote for case ID: {request.case_id}")
    
    # Extract token and authenticate the user
    try:
        token = credentials.credentials  # This is the raw JWT
        print(f"[DEBUG] Extracted JWT: {token}")
        
        print(f"[CASE_QUOTE] 🔐 Authenticating user...")
        user_response = await get_user_from_token(token)
        if not user_response["success"]:
            error_message = user_response.get("error", "Authentication required")
            print(f"[CASE_QUOTE] ❌ Authentication failed: {error_message}")
            raise HTTPException(status_code=401, detail=error_message)
        
        user_id = user_response["user"]["id"]
        user_role = user_response["user"].get("role", "")
        
        # Check if user is admin or teacher
        if user_role not in ["admin", "teacher"]:
            print(f"[CASE_QUOTE] ❌ Access denied: User role '{user_role}' is not authorized")
            raise HTTPException(status_code=403, detail="Only teachers and admins can update case quotes")
            
        print(f"[CASE_QUOTE] ✅ User authenticated successfully. User ID: {user_id}, Role: {user_role}")
    except HTTPException as auth_error:
        print(f"[CASE_QUOTE] ❌ HTTP exception during authentication: {str(auth_error)}")
        raise auth_error
    except Exception as auth_error:
        print(f"[CASE_QUOTE] ❌ Unexpected error during authentication: {str(auth_error)}")
        raise HTTPException(status_code=401, detail="Authentication failed")

    try:
        # Construct the path to the case cover file
        cover_file_path = Path(f"case-data/case{request.case_id}/case_cover.json")
        
        # Check if the file exists
        if not cover_file_path.exists():
            print(f"[CASE_QUOTE] ❌ Case cover file not found: {cover_file_path}")
            raise HTTPException(status_code=404, detail=f"Case cover file not found for case {request.case_id}")
        
        try:
            # Read the existing case cover data
            with open(cover_file_path, 'r') as f:
                case_cover_data = json.load(f)
        except json.JSONDecodeError as e:
            print(f"[CASE_QUOTE] ❌ Invalid JSON in case cover file: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Invalid JSON format in case cover file: {str(e)}"
            )
        
        # Update the quote and last_updated timestamp
        case_cover_data["quote"] = request.quote
        case_cover_data["last_updated"] = datetime.now().isoformat()
        
        try:
            # Write the updated data back to the file
            with open(cover_file_path, 'w') as f:
                json.dump(case_cover_data, f, indent=2)
        except Exception as write_error:
            print(f"[CASE_QUOTE] ❌ Error writing to case cover file: {str(write_error)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error writing to case cover file: {str(write_error)}"
            )
        
        print(f"[CASE_QUOTE] ✅ Successfully updated quote for case {request.case_id}")
        return {"message": "Case quote updated successfully"}
        
    except HTTPException as http_error:
        raise http_error
    except Exception as e:
        error_msg = str(e)
        print(f"[CASE_QUOTE] ❌ Error updating case quote: {error_msg}")
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred while updating the case quote: {error_msg}"
        ) 
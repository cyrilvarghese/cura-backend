from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, List
from datetime import datetime
import os
from pathlib import Path
import json
import shutil
from PIL import Image
import io
from auth.auth_api import get_user_from_token

# Define the security scheme
security = HTTPBearer()

router = APIRouter(
    prefix="/case-creator",
    tags=["case-creator"]
)

@router.post("/create")
async def create_case(
    case_data: dict,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Create a new case with the provided data.
    """
    print(f"[CASE_CREATOR] 📝 Creating new case with data: {case_data}")
    
    # Extract token and authenticate the user
    try:
        token = credentials.credentials  # This is the raw JWT
        print(f"[DEBUG] Extracted JWT: {token}")
        
        print(f"[CASE_CREATOR] 🔐 Authenticating user...")
        user_response = await get_user_from_token(token)
        if not user_response["success"]:
            error_message = user_response.get("error", "Authentication required")
            print(f"[CASE_CREATOR] ❌ Authentication failed: {error_message}")
            raise HTTPException(status_code=401, detail=error_message)
        
        user_id = user_response["user"]["id"]
        user_role = user_response["user"].get("role", "")
        
        # Check if user is admin or teacher
        if user_role not in ["admin", "teacher"]:
            print(f"[CASE_CREATOR] ❌ Access denied: User role '{user_role}' is not authorized")
            raise HTTPException(status_code=403, detail="Only teachers and admins can create cases")
            
        print(f"[CASE_CREATOR] ✅ User authenticated successfully. User ID: {user_id}, Role: {user_role}")
        
        try:
            # Your existing case creation logic here
            # ... existing code ...
            return {"message": "Case created successfully"}
        except Exception as e:
            print(f"[CASE_CREATOR] ❌ Error creating case: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error creating case: {str(e)}")
            
    except HTTPException as auth_error:
        print(f"[CASE_CREATOR] ❌ HTTP exception during authentication: {str(auth_error)}")
        raise auth_error
    except Exception as auth_error:
        print(f"[CASE_CREATOR] ❌ Unexpected error during authentication: {str(auth_error)}")
        raise HTTPException(status_code=401, detail="Authentication failed")

@router.get("/list")
async def list_cases(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    List all available cases.
    """
    print(f"[CASE_CREATOR] 📋 Listing all cases")
    
    # Extract token and authenticate the user
    try:
        token = credentials.credentials
        print(f"[DEBUG] Extracted JWT: {token}")
        
        print(f"[CASE_CREATOR] 🔐 Authenticating user...")
        user_response = await get_user_from_token(token)
        if not user_response["success"]:
            error_message = user_response.get("error", "Authentication required")
            print(f"[CASE_CREATOR] ❌ Authentication failed: {error_message}")
            raise HTTPException(status_code=401, detail=error_message)
        
        user_id = user_response["user"]["id"]
        print(f"[CASE_CREATOR] ✅ User authenticated successfully. User ID: {user_id}")
        
        try:
            # Your existing case listing logic here
            # ... existing code ...
            return {"message": "Cases listed successfully"}
        except Exception as e:
            print(f"[CASE_CREATOR] ❌ Error listing cases: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error listing cases: {str(e)}")
            
    except HTTPException as auth_error:
        print(f"[CASE_CREATOR] ❌ HTTP exception during authentication: {str(auth_error)}")
        raise auth_error
    except Exception as auth_error:
        print(f"[CASE_CREATOR] ❌ Unexpected error during authentication: {str(auth_error)}")
        raise HTTPException(status_code=401, detail="Authentication failed") 
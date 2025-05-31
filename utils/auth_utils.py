from fastapi import HTTPException
from typing import Tuple, Dict, Any
from auth.auth_api import get_user_from_token
from utils.session_manager import SessionManager

# Initialize a single instance of SessionManager to be shared
session_manager = SessionManager()

async def get_authenticated_session_data(token: str) -> Tuple[str, Dict[str, Any]]:
    """
    Helper function to get authenticated user's session data from a JWT token.
    
    Args:
        token (str): JWT token for authentication
        
    Returns:
        Tuple[str, Dict[str, Any]]: A tuple containing (student_id, session_data)
        
    Raises:
        HTTPException: If authentication fails or no active session is found
    """
    # Authenticate the user using the token
    user_response = await get_user_from_token(token)
    if not user_response["success"]:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    # Get the student ID from the authenticated user
    student_id = user_response["user"]["id"]
    
    # Retrieve session data for the student
    session_data = session_manager.get_session(student_id)
    if not session_data:
        raise HTTPException(status_code=404, detail="No active session found")
    
    return student_id, session_data 
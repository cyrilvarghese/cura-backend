from fastapi import Depends, HTTPException, status, Cookie, Header
from typing import Optional
from .auth_api import get_user_from_token, is_admin_from_token

async def get_current_user(
    authorization: Optional[str] = Header(None),
    access_token: Optional[str] = Cookie(None)
):
    """
    Get current user from Supabase JWT token (from Authorization header or cookie)
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    token = None
    
    # Try to get token from Authorization header first (standard approach)
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
    # Fall back to cookie
    elif access_token:
        token = access_token
    
    if not token:
        raise credentials_exception
    
    # Get user from Supabase token
    user_response = await get_user_from_token(token)
    
    if not user_response["success"]:
        raise credentials_exception
        
    return user_response["user"]

async def get_admin_user(current_user: dict = Depends(get_current_user)):
    """
    Ensure the current user is an admin
    """
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user

async def get_optional_user(
    authorization: Optional[str] = Header(None),
    access_token: Optional[str] = Cookie(None)
):
    """
    Get current user if token is provided, otherwise return None
    Useful for endpoints that work with or without authentication
    """
    token = None
    
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
    elif access_token:
        token = access_token
    
    if not token:
        return None
    
    try:
        user_response = await get_user_from_token(token)
        if user_response["success"]:
            return user_response["user"]
        return None
    except Exception:
        return None 
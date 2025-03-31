from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from typing import Optional, Dict, Any
from . import auth_api

# Create router
router = APIRouter(
    prefix="/auth",
    tags=["authentication"],
    responses={404: {"description": "Not found"}},
)

# Models
class UserCreate(BaseModel):
    email: str
    password: str
    username: str
    role: Optional[str] = "user"

class UserLogin(BaseModel):
    email: str
    password: str

# Routes
@router.post("/signup", response_model=Dict[str, Any])
async def signup(user: UserCreate):
    """
    Register a new user with email, password, username and role.
    """
    result = await auth_api.signup(user.email, user.password, user.username, user.role)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Signup failed"))
    return result

@router.post("/login", response_model=Dict[str, Any])
async def login(user: UserLogin):
    """
    Sign in a user with email and password.
    """
    result = await auth_api.login(user.email, user.password)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Login failed"))
    return result

@router.get("/user", response_model=Dict[str, Any])
async def get_user(authorization: Optional[str] = Header(None)):
    """
    Get the current logged-in user's information.
    """
    # Note: You may need to modify auth_api.get_user() to accept a token
    # if you want to implement token-based authentication
    result = await auth_api.get_user()
    if not result.get("success"):
        raise HTTPException(status_code=401, detail=result.get("error", "Authentication failed"))
    return result

@router.post("/logout", response_model=Dict[str, Any])
async def logout():
    """
    Sign out the current user.
    """
    result = await auth_a   pi.logout()
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Logout failed"))
    return result 
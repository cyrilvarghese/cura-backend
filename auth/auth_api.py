import os
from supabase import create_client, Client
from typing import Dict, Any, Optional
from dotenv import load_dotenv
import asyncio
from fastapi import HTTPException

# Load environment variables
load_dotenv()

# Initialize Supabase client once
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_supabase_client(use_service_role: bool = False) -> Client:
    """Initialize and validate Supabase client connection."""
    url = os.environ.get("SUPABASE_URL")
    
    if use_service_role:
        key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        if not key:
            raise EnvironmentError("SUPABASE_SERVICE_ROLE_KEY not configured")
    else:
        key = os.environ.get("SUPABASE_KEY")
        if not key:
            raise EnvironmentError("SUPABASE_KEY not configured")
    
    if not url:
        raise EnvironmentError("SUPABASE_URL not configured")
        
    return create_client(url, key)

# Initialize default client
supabase: Client = get_supabase_client()

async def signup(email: str, password: str, username: str, role: str = "user", invite_code: Optional[str] = None, timeout: int = 15) -> Dict[str, Any]:
    """
    Register a new user with email, password, username and role.
    
    Args:
        email: User's email
        password: User's password
        username: User's username
        role: User's role (defaults to "user")
        
    Returns:
        Dict containing user data and session
    """
    try:
        return await asyncio.wait_for(
            _signup_internal(email, password, username, role, invite_code),
            timeout=timeout
        )
    except asyncio.TimeoutError:
        print(f"Signup operation timed out after {timeout} seconds")
        return {
            "success": False,
            "error": "Operation timed out"
        }

async def _signup_internal(email: str, password: str, username: str, role: str, invite_code: Optional[str] = None):
    """Internal signup function wrapped with timeout"""
    try:
        print("\n=== Starting Signup Process ===")
        print(f"Email: {email}")
        print(f"Username: {username}")
        print(f"Role: {role}")
        print(f"Invite code: {invite_code}")
        # Create service client for bypassing RLS
        service_role_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        if not service_role_key:
            print("❌ Error: SUPABASE_SERVICE_ROLE_KEY not found in environment variables")
            raise Exception("Service role key not configured")
            
        service_client = create_client(SUPABASE_URL, service_role_key)
        print("✓ Service client created successfully")
        
        # Create the user in Supabase Auth
        print("\n=== Creating User ===")
        auth_response = supabase.auth.sign_up({
            "email": email,
            "password": password,
        })
        
        print(f"Auth response user: {auth_response.user}")
        
        if auth_response.user:
            user_id = auth_response.user.id
            print(f"✓ User created with ID: {user_id}")
            
            try:
                # Insert profile using service client to bypass RLS
                profile_data = {
                    "id": user_id,
                    "username": username,
                    "role": role,
                    "email": email,
                    "invite_code": invite_code if invite_code else None
                }
                print(f"Inserting profile data: {profile_data}")
                
                profile_response = service_client.table("profiles").insert(profile_data).execute()
                print(f"✓ Profile created successfully: {profile_response}")
                
                # Return Supabase's JWT token directly
                return {
                    "success": True,
                    "access_token": auth_response.session.access_token,
                    "refresh_token": auth_response.session.refresh_token,
                    "token_type": "bearer",
                    "expires_at": auth_response.session.expires_at,
                    "user": {
                        "id": user_id,
                        "email": email,
                        "username": username,
                        "role": role,
                        "invite_code": invite_code if invite_code else None
                    }
                }
            except Exception as profile_error:
                print(f"❌ Error inserting profile: {str(profile_error)}")
                return {
                    "success": False,
                    "error": str(profile_error)
                }
        else:
            print("❌ No user object in auth response")
            return {
                "success": False,
                "error": "Failed to create user"
            }
    except Exception as e:
        print(f"❌ Signup error: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

async def login(email: str, password: str, timeout: int = 15) -> Dict[str, Any]:
    """Sign in a user with email and password."""
    try:
        return await asyncio.wait_for(
            _login_internal(email, password),
            timeout=timeout
        )
    except asyncio.TimeoutError:
        print(f"Login operation timed out after {timeout} seconds")
        return {
            "success": False,
            "error": "Operation timed out"
        }

async def _login_internal(email: str, password: str):
    """Internal login function wrapped with timeout"""
    try:
        # Sign in the user
        auth_response = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
        
        if auth_response.user and auth_response.session:
            # Get the user's profile data
            profile_response = supabase.table("profiles").select("*").eq("id", auth_response.user.id).execute()
            
            if profile_response.data and len(profile_response.data) > 0:
                profile = profile_response.data[0]
                
                user_data = {
                    "id": auth_response.user.id,
                    "email": email,
                    "username": profile.get("username"),
                    "role": profile.get("role")
                }
                
                print("Login successful. Supabase JWT token issued for user:", user_data["email"])
                
                # Return Supabase's JWT tokens
                return {
                    "success": True,
                    "access_token": auth_response.session.access_token,
                    "refresh_token": auth_response.session.refresh_token,
                    "token_type": "bearer",
                    "expires_at": auth_response.session.expires_at,
                    "user": user_data
                }
            
        return {
            "success": False,
            "error": "Invalid credentials"
        }
    except Exception as e:
        print(f"Login error: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

async def get_user_from_token(access_token: str) -> Dict[str, Any]:
    """
    Get user information from Supabase JWT token.
    
    Args:
        access_token: Supabase JWT access token
        
    Returns:
        Dict containing user data
    """
    try:
        # Create a new client with the user's token
        user_client = create_client(SUPABASE_URL, SUPABASE_KEY)
        
        # Don't set session, just get user directly from token
        user_response = user_client.auth.get_user(access_token)
        
        if user_response.user:
            user_id = user_response.user.id
            
            # Get the user's profile data using the authenticated client
            # Set the Authorization header manually for this request
            user_client.postgrest.auth(access_token)
            profile_response = user_client.table("profiles").select("*").eq("id", user_id).execute()
            
            if profile_response.data and len(profile_response.data) > 0:
                profile = profile_response.data[0]
                
                user_data = {
                    "id": user_id,
                    "email": user_response.user.email,
                    "username": profile.get("username"),
                    "role": profile.get("role")
                }
                
                return {
                    "success": True,
                    "user": user_data
                }
            else:
                # Fallback to basic user data if no profile
                user_data = {
                    "id": user_id,
                    "email": user_response.user.email,
                    "username": None,
                    "role": None
                }
                
                return {
                    "success": True,
                    "user": user_data
                }
        else:
            return {
                "success": False,
                "error": "Invalid or expired token"
            }
            
    except Exception as e:
        print(f"Error getting user from token: {str(e)}")
        return {
            "success": False,
            "error": "Invalid or expired token"
        }

# Remove the old get_user function that relied on global state
async def get_user() -> Dict[str, Any]:
    """
    DEPRECATED: Use get_user_from_token instead.
    """
    return {
        "success": False,
        "error": "This function is deprecated. Use token-based authentication instead."
    }

async def logout(timeout: int = 15) -> Dict[str, Any]:
    """
    Sign out the current user.
    """
    try:
        # With Supabase, logout is handled client-side by clearing the token
        # The token will naturally expire based on Supabase's settings
        print("User logged out (token should be cleared client-side)")
        
        return {
            "success": True,
            "message": "Logged out successfully"
        }
    except Exception as e:
        print(f"Logout error: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

def get_authenticated_client(access_token: str) -> Client:
    """Get a Supabase client with the user's JWT token"""
    try:
        # Create client with user's token
        user_client = create_client(SUPABASE_URL, SUPABASE_KEY)
        user_client.auth.set_session(access_token, None)
        
        return user_client
        
    except Exception as e:
        print(f"Authentication error: {str(e)}")
        raise Exception("Authentication required. Please log in.")

async def is_admin_from_token(access_token: str) -> bool:
    """
    Check if the user with the given token has admin privileges.
    """
    try:
        user_response = await get_user_from_token(access_token)
        
        if not user_response["success"]:
            print(f"Admin check failed: {user_response.get('error', 'User not authenticated')}")
            return False
        
        user_role = user_response["user"].get("role")
        is_admin_role = user_role == "admin"
        
        print(f"Admin check: User role is '{user_role}', admin status: {is_admin_role}")
        return is_admin_role
        
    except Exception as e:
        print(f"Error checking admin status: {str(e)}")
        return False 
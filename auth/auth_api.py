import os
from supabase import create_client, Client
from typing import Dict, Any, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Global variables to store session info
current_session = None
current_user = None

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

async def signup(email: str, password: str, username: str, role: str = "user") -> Dict[str, Any]:
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
        print("\n=== Starting Signup Process ===")
        print(f"Email: {email}")
        print(f"Username: {username}")
        print(f"Role: {role}")
        
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
                    "email": email
                }
                print(f"Inserting profile data: {profile_data}")
                
                profile_response = service_client.table("profiles").insert(profile_data).execute()
                print(f"✓ Profile created successfully: {profile_response}")
                
                return {
                    "success": True,
                    "token": auth_response.session.access_token if auth_response.session else None,
                    "user": {
                        "id": user_id,
                        "email": email,
                        "username": username,
                        "role": role
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

async def login(email: str, password: str) -> Dict[str, Any]:
    """Sign in a user with email and password."""
    try:
        global current_session, current_user
        
        # Sign in the user with session options
        auth_response = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
        
        if auth_response.user:
            # Get the user's profile data
            profile_response = supabase.table("profiles").select("*").eq("id", auth_response.user.id).execute()
            
            if profile_response.data and len(profile_response.data) > 0:
                profile = profile_response.data[0]
                
                # Store session info
                current_session = auth_response.session
                current_user = {
                    "id": auth_response.user.id,
                    "email": email,
                    "username": profile.get("username"),
                    "role": profile.get("role")
                }
                
                print("Login successful. Session info:", {
                    "user": current_user["email"],
                    "access_token_expires_at": current_session.expires_at if current_session else None,
                    "has_refresh_token": bool(current_session.refresh_token) if current_session else False
                })
                
                return {
                    "success": True,
                    "token": auth_response.session.access_token if auth_response.session else None,
                    "refresh_token": auth_response.session.refresh_token if auth_response.session else None,
                    "user": current_user
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

async def get_user() -> Dict[str, Any]:
    """
    Get the current logged-in user's information.
    
    Returns:
        Dict containing user data
    """
    try:
        global current_session, current_user
        
        # If we have cached user info, return it
        if current_user and current_session:
            return {
                "success": True,
                "user": current_user
            }
            
        # Otherwise get the current session
        session = supabase.auth.get_session()
        
        if not session or not session.user:
            return {
                "success": False,
                "error": "No active session found"
            }
        
        user_id = session.user.id
        
        # Get the user's profile data
        profile_response = supabase.table("profiles").select("*").eq("id", user_id).execute()
        
        if profile_response.data and len(profile_response.data) > 0:
            profile = profile_response.data[0]
            
            # Store session info globally
            current_session = session
            current_user = {
                "id": user_id,
                "email": session.user.email,
                "username": profile.get("username"),
                "role": profile.get("role")
            }
            
            return {
                "success": True,
                "user": current_user
            }
        else:
            current_user = {
                "id": user_id,
                "email": session.user.email
            }
            return {
                "success": True,
                "user": current_user
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

async def logout() -> Dict[str, Any]:
    """
    Sign out the current user and clear session data.
    
    Returns:
        Dict indicating success or failure
    """
    try:
        global current_session, current_user
        
        # Log current state before clearing
        print("Logging out user:", {
            "email": current_user.get("email") if current_user else None,
            "role": current_user.get("role") if current_user else None
        })
        
        # Sign out from Supabase
        supabase.auth.sign_out()
        
        # Clear session info
        current_session = None
        current_user = None
        
        print("Session cleared - current_session and current_user set to None")
        
        return {
            "success": True
        }
    except Exception as e:
        print(f"Logout error: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

# Add this helper function to get authenticated client
def get_authenticated_client() -> Client:
    """Get a Supabase client with the current user's session"""
    global current_session, current_user, supabase

    try:
        if not current_session or not current_user:
            print("No active session found, attempting to refresh...")
            # Try to get session from Supabase
            session_response = supabase.auth.get_session()

            if session_response and session_response.session:
                current_session = session_response.session
                user = session_response.user
                if user:
                    current_user = {
                        "id": user.id,
                        "email": user.email,
                        "role": user.user_metadata.get("role") if user.user_metadata else None
                    }
                    print(f"Session refreshed for user: {current_user['email']}")
                else:
                    raise Exception("No user data in session")
            else:
                raise Exception("No valid session found")

        # Always try to refresh the session if access token is close to expiring
        try:
            refresh_response = supabase.auth.refresh_session()
            if refresh_response and refresh_response.session:
                current_session = refresh_response.session
                print("Session refreshed successfully")
        except Exception as refresh_error:
            print(f"Session refresh failed: {str(refresh_error)}")

        # Set the session on the client
        supabase.auth.set_session(
            current_session.access_token,
            current_session.refresh_token
        )

        print(f"Using authenticated session for user: {current_user['email']}")
        return supabase
    except Exception as e:
        print(f"Authentication error: {str(e)}")
        raise Exception("Authentication required. Please log in.")

# Simple function to get the client
def get_client() -> Client:
    """Get the Supabase client"""
    return supabase 
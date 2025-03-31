import os
from supabase import create_client, Client
from typing import Dict, Any, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Supabase client
supabase_url = os.environ.get("SUPABASE_URL")
supabase_key = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(supabase_url, supabase_key)

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
            
        service_client = create_client(supabase_url, service_role_key)
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
    """
    Sign in a user with email and password.
    
    Args:
        email: User's email
        password: User's password
        
    Returns:
        Dict containing user data and session
    """
    try:
        # Sign in the user
        auth_response = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
        
        if auth_response.user:
            # Get the user's profile data
            profile_response = supabase.table("profiles").select("*").eq("id", auth_response.user.id).execute()
            
            if profile_response.data and len(profile_response.data) > 0:
                profile = profile_response.data[0]
                
                return {
                    "success": True,
                    "token": auth_response.session.access_token if auth_response.session else None,
                    "user": {
                        "id": auth_response.user.id,
                        "email": email,
                        "username": profile.get("username"),
                        "role": profile.get("role")
                    }
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
        # Get the current session
        session = supabase.auth.get_session()
        
        if not session or not session.user:
            return {
                "success": False,
                "error": "No active session found"
            }
        
        user_id = session.user.id
        
        # Get the user's profile data from the profiles table
        profile_response = supabase.table("profiles").select("*").eq("id", user_id).execute()
        
        if profile_response.data and len(profile_response.data) > 0:
            profile = profile_response.data[0]
            
            return {
                "success": True,
                "user": {
                    "id": user_id,
                    "email": session.user.email,
                    "username": profile.get("username"),
                    "role": profile.get("role")
                }
            }
        else:
            return {
                "success": True,
                "user": {
                    "id": user_id,
                    "email": session.user.email
                }
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

async def logout() -> Dict[str, Any]:
    """
    Sign out the current user.
    
    Returns:
        Dict indicating success or failure
    """
    try:
        supabase.auth.sign_out()
        return {
            "success": True
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        } 
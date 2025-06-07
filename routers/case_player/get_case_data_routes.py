from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Dict, Any, List
import json
import os
import shutil
from pathlib import Path
from datetime import datetime
from utils.session_manager import SessionManager
from auth.auth_api import get_user, get_authenticated_client, get_user_from_token

case_router = APIRouter()
session_manager = SessionManager()

# Define the security scheme
security = HTTPBearer()

class CaseData(BaseModel):
    content: Dict[str, Any]

class CaseInfo(BaseModel):
    case_id: int
    case_name: str
    title: str | None = None
    quote: str | None = None
    image_url: str | None = None
    last_updated: str | None = None
    differential_diagnosis: list[str] | None = None
    department: str | None = None
    published: bool | None = None
    deleted: bool | None = None

class CaseCoverUpdate(BaseModel):
    published: bool

class CaseDeleteUpdate(BaseModel):
    deleted: bool

@case_router.get("/cases", response_model=List[CaseInfo])
async def list_cases(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """List all available cases by reading case_cover.json files"""
    print(f"[CASE_ROUTER] 📋 Getting list of cases...")
    
    # Extract token and authenticate the user
    try:
        token = credentials.credentials  # This is the raw JWT
        print(f"[DEBUG] Extracted JWT: {token}")
        
        print(f"[CASE_ROUTER] 🔐 Authenticating user...")
        user_response = await get_user_from_token(token)
        if not user_response["success"]:
            error_message = user_response.get("error", "Authentication required")
            print(f"[CASE_ROUTER] ❌ Authentication failed: {error_message}")
            raise HTTPException(status_code=401, detail=error_message)
        
        user_id = user_response["user"]["id"]
        print(f"[CASE_ROUTER] ✅ User authenticated successfully. User ID: {user_id}")
    except HTTPException as auth_error:
        print(f"[CASE_ROUTER] ❌ HTTP exception during authentication: {str(auth_error)}")
        raise auth_error
    except Exception as auth_error:
        print(f"[CASE_ROUTER] ❌ Unexpected error during authentication: {str(auth_error)}")
        raise HTTPException(status_code=401, detail="Authentication failed")

    try:
        cases = []
        case_data_dir = Path("case-data")
        
        # Iterate through all case folders
        for case_dir in sorted(case_data_dir.glob("case*")):
            cover_file = case_dir / "case_cover.json"
            if cover_file.exists():
                try:
                    with open(cover_file, "r") as f:
                        cover_data = json.load(f)
                        case_info = CaseInfo(
                            case_id=cover_data.get("case_id", 0),
                            case_name=cover_data["case_name"],
                            title=cover_data.get("title"),
                            quote=cover_data.get("quote"),
                            image_url=cover_data.get("image_url"),
                            last_updated=cover_data.get("last_updated"),
                            differential_diagnosis=cover_data.get("differential_diagnosis"),
                            department=cover_data.get("department"),
                            published=cover_data.get("published"),
                            deleted=cover_data.get("deleted")
                        )
                        cases.append(case_info)
                except json.JSONDecodeError as e:
                    print(f"Error parsing JSON in {cover_file}: {e}")
                    continue
                except KeyError as e:
                    print(f"Missing required field in {cover_file}: {e}")
                    continue
        
        # Sort cases by case_id
        cases.sort(key=lambda x: x.case_id)
        print(f"[CASE_ROUTER] ✅ Retrieved {len(cases)} cases successfully")
        return cases

    except HTTPException as http_error:
        raise http_error
    except Exception as e:
        error_msg = str(e)
        print(f"[CASE_ROUTER] ❌ Error retrieving cases: {error_msg}")
        raise HTTPException(status_code=500, detail=f"Error retrieving case list: {error_msg}")

@case_router.get("/cases/{case_id}", response_model=CaseData)
async def get_case_data(case_id: str, credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get case data including physical exam and lab test data"""
    print(f"[CASE_ROUTER] 📊 Getting case data for case ID: {case_id}")
    
    # Extract token and authenticate the user
    try:
        token = credentials.credentials  # This is the raw JWT
        print(f"[DEBUG] Extracted JWT: {token}")
        
        print(f"[CASE_ROUTER] 🔐 Authenticating user...")
        user_response = await get_user_from_token(token)
        if not user_response["success"]:
            error_message = user_response.get("error", "Authentication required")
            print(f"[CASE_ROUTER] ❌ Authentication failed: {error_message}")
            raise HTTPException(status_code=401, detail=error_message)
        
        student_id = user_response["user"]["id"]
        print(f"[CASE_ROUTER] ✅ User authenticated successfully. Student ID: {student_id}")
    except HTTPException as auth_error:
        print(f"[CASE_ROUTER] ❌ HTTP exception during authentication: {str(auth_error)}")
        raise auth_error
    except Exception as auth_error:
        print(f"[CASE_ROUTER] ❌ Unexpected error during authentication: {str(auth_error)}")
        raise HTTPException(status_code=401, detail="Authentication failed")

    try:
        # Clear the session for this student-case combination
        session_manager.clear_session(student_id, case_id)
        
        # Define paths for the case data and case cover
        data_file_path = os.path.join('case-data', f'case{case_id}', 'test_exam_data.json')
        cover_file_path = os.path.join('case-data', f'case{case_id}', 'case_cover.json')
        diagnosis_context_path = os.path.join('case-data', f'case{case_id}', 'diagnosis_context.json')
        
        # Check if files exist
        if not os.path.exists(data_file_path):
            raise HTTPException(status_code=404, detail=f"Case exam data not found for case {case_id}")
        if not os.path.exists(cover_file_path):
            raise HTTPException(status_code=404, detail=f"Case cover data not found for case {case_id}")
        
        try:
            # Load the case data
            with open(data_file_path, 'r') as file:
                data = json.load(file)
            with open(cover_file_path, 'r') as cover_file:
                case_cover_data = json.load(cover_file)
                
            # Load diagnosis context if available
            diagnosis_context_data = {}
            if os.path.exists(diagnosis_context_path):
                try:
                    with open(diagnosis_context_path, 'r') as context_file:
                        diagnosis_context_data = json.load(context_file)
                except json.JSONDecodeError as json_error:
                    print(f"Invalid JSON in diagnosis_context.json: {str(json_error)}")
                except Exception as file_error:
                    print(f"Error reading diagnosis_context.json: {str(file_error)}")
        except json.JSONDecodeError as json_error:
            raise HTTPException(
                status_code=500,
                detail=f"Invalid JSON format in case files: {str(json_error)}"
            )
        except Exception as file_error:
            raise HTTPException(
                status_code=500,
                detail=f"Error reading case files: {str(file_error)}"
            )

        print(f"[CASE_ROUTER] ✅ Successfully retrieved case data for case {case_id}")
        return {
            "content": {
                "physical_exam": data.get("physical_exam", {}),
                "lab_test": data.get("lab_test", {}),
                "case_cover": case_cover_data,
                "diagnosis_context": diagnosis_context_data
            }
        }
        
    except HTTPException as http_error:
        raise http_error
    except Exception as e:
        error_msg = str(e)
        print(f"[CASE_ROUTER] ❌ Error retrieving case data: {error_msg}")
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred while processing the case data: {error_msg}"
        )

@case_router.post("/cases/{case_id}/publish", response_model=dict)
async def update_case_cover(case_id: str, update_data: CaseCoverUpdate, credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Update published status in the case cover file"""
    print(f"[CASE_ROUTER] 📝 Updating case cover for case ID: {case_id}")
    
    # Extract token and authenticate the user
    try:
        token = credentials.credentials  # This is the raw JWT
        print(f"[DEBUG] Extracted JWT: {token}")
        
        print(f"[CASE_ROUTER] 🔐 Authenticating user...")
        user_response = await get_user_from_token(token)
        if not user_response["success"]:
            error_message = user_response.get("error", "Authentication required")
            print(f"[CASE_ROUTER] ❌ Authentication failed: {error_message}")
            raise HTTPException(status_code=401, detail=error_message)
        
        user_id = user_response["user"]["id"]
        print(f"[CASE_ROUTER] ✅ User authenticated successfully. User ID: {user_id}")
    except HTTPException as auth_error:
        print(f"[CASE_ROUTER] ❌ HTTP exception during authentication: {str(auth_error)}")
        raise auth_error
    except Exception as auth_error:
        print(f"[CASE_ROUTER] ❌ Unexpected error during authentication: {str(auth_error)}")
        raise HTTPException(status_code=401, detail="Authentication failed")

    try:
        cover_file_path = os.path.join('case-data', f'case{case_id}', 'case_cover.json')
        
        # Check if the case cover file exists
        if not os.path.exists(cover_file_path):
            raise HTTPException(status_code=404, detail=f"Case cover data not found for case {case_id}")
        
        try:
            # Read existing case cover data
            with open(cover_file_path, 'r') as f:
                case_cover_data = json.load(f)
        except json.JSONDecodeError as e:
            raise HTTPException(
                status_code=500,
                detail=f"Invalid JSON format in case cover file: {str(e)}"
            )
        
        # Update published status and timestamp
        case_cover_data["published"] = update_data.published
        case_cover_data["last_updated"] = datetime.now().isoformat()
        
        try:
            # Write updated data back to the file
            with open(cover_file_path, 'w') as f:
                json.dump(case_cover_data, f, indent=2)
        except Exception as write_error:
            raise HTTPException(
                status_code=500,
                detail=f"Error writing to case cover file: {str(write_error)}"
            )
        
        # Reset the last_modified_time in Supabase
        try:
            supabase = get_authenticated_client()
            case_name = case_cover_data.get("case_name")
            if case_name:
                result = supabase.table("documents")\
                    .update({"last_modified_time": None})\
                    .eq("title", case_name)\
                    .execute()
                print(f"Reset result: {result.data}")
        except Exception as db_error:
            print(f"WARNING: Could not reset last_modified_time in Supabase: {str(db_error)}")
            # Don't raise HTTP exception here as this is not critical
        
        print(f"[CASE_ROUTER] ✅ Case cover updated successfully for case {case_id}")
        return {"message": "Case cover updated successfully"}

    except HTTPException as http_error:
        raise http_error
    except Exception as e:
        error_msg = str(e)
        print(f"[CASE_ROUTER] ❌ Error updating case cover: {error_msg}")
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred while updating the case cover: {error_msg}"
        )

@case_router.post("/cases/{case_id}/unpublish", response_model=dict)
async def unpublish_case(case_id: str, credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Unpublish a case by setting published status to false"""
    print(f"[CASE_ROUTER] 📝 Unpublishing case ID: {case_id}")
    
    # Extract token and authenticate the user
    try:
        token = credentials.credentials  # This is the raw JWT
        print(f"[DEBUG] Extracted JWT: {token}")
        
        print(f"[CASE_ROUTER] 🔐 Authenticating user...")
        user_response = await get_user_from_token(token)
        if not user_response["success"]:
            error_message = user_response.get("error", "Authentication required")
            print(f"[CASE_ROUTER] ❌ Authentication failed: {error_message}")
            raise HTTPException(status_code=401, detail=error_message)
        
        user_id = user_response["user"]["id"]
        print(f"[CASE_ROUTER] ✅ User authenticated successfully. User ID: {user_id}")
    except HTTPException as auth_error:
        print(f"[CASE_ROUTER] ❌ HTTP exception during authentication: {str(auth_error)}")
        raise auth_error
    except Exception as auth_error:
        print(f"[CASE_ROUTER] ❌ Unexpected error during authentication: {str(auth_error)}")
        raise HTTPException(status_code=401, detail="Authentication failed")

    try:
        cover_file_path = os.path.join('case-data', f'case{case_id}', 'case_cover.json')
        
        # Check if the case cover file exists
        if not os.path.exists(cover_file_path):
            raise HTTPException(status_code=404, detail=f"Case cover data not found for case {case_id}")
        
        try:
            # Read existing case cover data
            with open(cover_file_path, 'r') as f:
                case_cover_data = json.load(f)
        except json.JSONDecodeError as e:
            raise HTTPException(
                status_code=500,
                detail=f"Invalid JSON format in case cover file: {str(e)}"
            )
        
        # Set published status to false and update timestamp
        case_cover_data["published"] = False
        case_cover_data["last_updated"] = datetime.now().isoformat()
        
        try:
            # Write updated data back to the file
            with open(cover_file_path, 'w') as f:
                json.dump(case_cover_data, f, indent=2)
        except Exception as write_error:
            raise HTTPException(
                status_code=500,
                detail=f"Error writing to case cover file: {str(write_error)}"
            )
        
        # Reset the last_modified_time in Supabase
        try:
            supabase = get_authenticated_client()
            case_name = case_cover_data.get("case_name")
            if case_name:
                result = supabase.table("documents")\
                    .update({"last_modified_time": None})\
                    .eq("title", case_name)\
                    .execute()
                print(f"Reset result: {result.data}")
        except Exception as db_error:
            print(f"WARNING: Could not reset last_modified_time in Supabase: {str(db_error)}")
            # Don't raise HTTP exception here as this is not critical
        
        print(f"[CASE_ROUTER] ✅ Case unpublished successfully for case {case_id}")
        return {"message": "Case unpublished successfully"}

    except HTTPException as http_error:
        raise http_error
    except Exception as e:
        error_msg = str(e)
        print(f"[CASE_ROUTER] ❌ Error unpublishing case: {error_msg}")
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred while unpublishing the case: {error_msg}"
        )

@case_router.post("/cases/{case_id}/delete", response_model=dict)
async def soft_delete_case(case_id: str, update_data: CaseDeleteUpdate, credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Mark a case as deleted (soft delete) by updating the deleted flag and moving to deleted folder"""
    print(f"[CASE_ROUTER] 🗑️ Soft deleting case ID: {case_id}")
    
    # Extract token and authenticate the user
    try:
        token = credentials.credentials  # This is the raw JWT
        print(f"[DEBUG] Extracted JWT: {token}")
        
        print(f"[CASE_ROUTER] 🔐 Authenticating user...")
        user_response = await get_user_from_token(token)
        if not user_response["success"]:
            error_message = user_response.get("error", "Authentication required")
            print(f"[CASE_ROUTER] ❌ Authentication failed: {error_message}")
            raise HTTPException(status_code=401, detail=error_message)
        
        user_id = user_response["user"]["id"]
        print(f"[CASE_ROUTER] ✅ User authenticated successfully. User ID: {user_id}")
    except HTTPException as auth_error:
        print(f"[CASE_ROUTER] ❌ HTTP exception during authentication: {str(auth_error)}")
        raise auth_error
    except Exception as auth_error:
        print(f"[CASE_ROUTER] ❌ Unexpected error during authentication: {str(auth_error)}")
        raise HTTPException(status_code=401, detail="Authentication failed")

    try:
        case_folder_path = os.path.join('case-data', f'case{case_id}')
        cover_file_path = os.path.join(case_folder_path, 'case_cover.json')
        
        # Check if the case folder exists
        if not os.path.exists(case_folder_path):
            raise HTTPException(status_code=404, detail=f"Case folder not found for case {case_id}")
        
        # Check if the case cover file exists
        if not os.path.exists(cover_file_path):
            raise HTTPException(status_code=404, detail=f"Case cover data not found for case {case_id}")
        
        try:
            # Read existing case cover data
            with open(cover_file_path, 'r') as f:
                case_cover_data = json.load(f)
        except json.JSONDecodeError as e:
            raise HTTPException(
                status_code=500,
                detail=f"Invalid JSON format in case cover file: {str(e)}"
            )
        
        if update_data.deleted:
            # Mark as deleted and move to deleted folder
            case_cover_data["deleted"] = True
            case_cover_data["last_updated"] = datetime.now().isoformat()
            
            # Write updated data back to the file before moving
            try:
                with open(cover_file_path, 'w') as f:
                    json.dump(case_cover_data, f, indent=2)
            except Exception as write_error:
                raise HTTPException(
                    status_code=500,
                    detail=f"Error writing to case cover file: {str(write_error)}"
                )
            
            # Create deleted folder if it doesn't exist
            deleted_folder_path = os.path.join('case-data', 'deleted')
            os.makedirs(deleted_folder_path, exist_ok=True)
            
            # Move the case folder to deleted folder
            destination_path = os.path.join(deleted_folder_path, f'case{case_id}')
            
            # If destination already exists, remove it first
            if os.path.exists(destination_path):
                shutil.rmtree(destination_path)
            
            try:
                shutil.move(case_folder_path, destination_path)
                print(f"[CASE_ROUTER] ✅ Case folder moved to deleted directory: {destination_path}")
            except Exception as move_error:
                raise HTTPException(
                    status_code=500,
                    detail=f"Error moving case folder to deleted directory: {str(move_error)}"
                )
            
        else:
            # Restore from deleted folder
            deleted_folder_path = os.path.join('case-data', 'deleted')
            deleted_case_path = os.path.join(deleted_folder_path, f'case{case_id}')
            
            if os.path.exists(deleted_case_path):
                # Move back from deleted folder
                try:
                    shutil.move(deleted_case_path, case_folder_path)
                    print(f"[CASE_ROUTER] ✅ Case folder restored from deleted directory: {case_folder_path}")
                except Exception as move_error:
                    raise HTTPException(
                        status_code=500,
                        detail=f"Error restoring case folder from deleted directory: {str(move_error)}"
                    )
                
                # Update the case cover file in the restored location
                restored_cover_file_path = os.path.join(case_folder_path, 'case_cover.json')
                try:
                    with open(restored_cover_file_path, 'r') as f:
                        case_cover_data = json.load(f)
                    
                    case_cover_data["deleted"] = False
                    case_cover_data["last_updated"] = datetime.now().isoformat()
                    
                    with open(restored_cover_file_path, 'w') as f:
                        json.dump(case_cover_data, f, indent=2)
                except Exception as restore_error:
                    raise HTTPException(
                        status_code=500,
                        detail=f"Error updating restored case cover file: {str(restore_error)}"
                    )
            else:
                # Case not found in deleted folder, just update the flag
                case_cover_data["deleted"] = False
                case_cover_data["last_updated"] = datetime.now().isoformat()
                
                try:
                    with open(cover_file_path, 'w') as f:
                        json.dump(case_cover_data, f, indent=2)
                except Exception as write_error:
                    raise HTTPException(
                        status_code=500,
                        detail=f"Error writing to case cover file: {str(write_error)}"
                    )
        
        action = "deleted and moved to deleted folder" if update_data.deleted else "restored from deleted folder"
        print(f"[CASE_ROUTER] ✅ Case {action} successfully for case {case_id}")
        return {"message": f"Case {action} successfully"}

    except HTTPException as http_error:
        raise http_error
    except Exception as e:
        error_msg = str(e)
        print(f"[CASE_ROUTER] ❌ Error updating case deletion status: {error_msg}")
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred while updating the case deletion status: {error_msg}"
        )
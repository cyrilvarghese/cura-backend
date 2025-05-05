from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List
import json
import os
from pathlib import Path
from datetime import datetime
from utils.session_manager import SessionManager
from auth.auth_api import get_user, get_authenticated_client

case_router = APIRouter()
session_manager = SessionManager()

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
async def list_cases():
    """List all available cases by reading case_cover.json files"""
    try:
        # First check authentication
        user_response = await get_user()
        if not user_response["success"]:
            error_message = user_response.get("error", "Authentication required")
            raise HTTPException(status_code=401, detail=error_message)

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
        return cases

    except HTTPException as http_error:
        raise http_error
    except Exception as e:
        print(f"Unexpected error in list_cases: {str(e)}")
        raise HTTPException(status_code=500, detail="Error retrieving case list")

@case_router.get("/cases/{case_id}", response_model=CaseData)
async def get_case_data(case_id: str):
    """Get case data including physical exam and lab test data"""
    # First handle authentication outside main try block
    try:
        user_response = await get_user()
        if not user_response["success"]:
            error_message = user_response.get("error", "Authentication required")
            raise HTTPException(status_code=401, detail=error_message)
        
        student_id = user_response["user"]["id"]
    except HTTPException as auth_error:
        raise auth_error
    except Exception as auth_error:
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
        print(f"Unexpected error in get_case_data: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while processing the case data"
        )

@case_router.post("/cases/{case_id}/publish", response_model=dict)
async def update_case_cover(case_id: str, update_data: CaseCoverUpdate):
    """Update published status in the case cover file"""
    try:
        # First check authentication
        user_response = await get_user()
        if not user_response["success"]:
            error_message = user_response.get("error", "Authentication required")
            raise HTTPException(status_code=401, detail=error_message)

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
        
        return {"message": "Case cover updated successfully"}

    except HTTPException as http_error:
        raise http_error
    except Exception as e:
        print(f"Unexpected error in update_case_cover: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while updating the case cover"
        )

@case_router.post("/cases/{case_id}/delete", response_model=dict)
async def soft_delete_case(case_id: str, update_data: CaseDeleteUpdate):
    """Mark a case as deleted (soft delete) by updating the deleted flag in the case cover file"""
    try:
        # First check authentication
        user_response = await get_user()
        if not user_response["success"]:
            error_message = user_response.get("error", "Authentication required")
            raise HTTPException(status_code=401, detail=error_message)

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
        
        # Update deleted status and timestamp
        case_cover_data["deleted"] = update_data.deleted
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
        
        return {"message": "Case deletion status updated successfully"}

    except HTTPException as http_error:
        raise http_error
    except Exception as e:
        print(f"Unexpected error in soft_delete_case: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while updating the case deletion status"
        )
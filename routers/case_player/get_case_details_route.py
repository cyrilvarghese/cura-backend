from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Dict, Any
import json
import os
import traceback
import dateutil.parser
import shutil
from auth.auth_api import get_user_from_token

from routers.curriculum import get_db_connection

# Define the security scheme
security = HTTPBearer()

router = APIRouter(
    prefix="/case-details",
    tags=["case-player"]
)

class CaseDetailsResponse(BaseModel):
    content: Dict[str, Any]

def update_case_doc_from_uploads(case_id: str) -> bool:
    """
    Update the case_doc.txt file from the @uploads folder for the given case_id.
    Returns True if successfully updated, False otherwise.
    """
    try:
        # Get case_cover.json path
        case_base_path = os.path.join('case-data', f'case{case_id}')
        cover_file_path = os.path.join(case_base_path, 'case_cover.json')
        
        # Check if cover file exists
        if not os.path.exists(cover_file_path):
            print(f"ERROR: Case cover file not found at: {cover_file_path}")
            return False
            
        # Read case_cover.json to get case_name
        with open(cover_file_path, 'r') as file:
            case_data = json.load(file)
            case_name = case_data.get('case_name')
            
        if not case_name:
            print(f"ERROR: No case_name found in case cover file")
            return False
            
        # Get uploads directory from environment variable
        upload_dir = os.getenv("UPLOADS_DIR", "case-data/uploads")
        
        # Look for the exact file with the extension as specified in case_name
        file_path = os.path.join(upload_dir, case_name)
        
        if not os.path.exists(file_path):
            print(f"WARNING: File not found in uploads: {file_path}")
            return False
            
        # Copy the found file to case_doc.txt in the case folder
        target_path = os.path.join(case_base_path, 'case_doc.txt')
        
        # If the file is a text file or markdown, copy content directly
        if file_path.endswith(('.txt', '.md')):
            with open(file_path, 'r', encoding='utf-8') as source:
                content = source.read()
                with open(target_path, 'w', encoding='utf-8') as target:
                    target.write(content)
            print(f"SUCCESS: Copied text content from {file_path} to case_doc.txt")
        # For other file types, perform direct file copy
        else:
            print(f"NOTE: Non-text file found ({file_path}). Direct copy performed.")
            shutil.copy2(file_path, target_path)
            
        print(f"SUCCESS: Updated case_doc.txt for case {case_id} from {file_path}")
        return True
        
    except Exception as e:
        print(f"ERROR updating case_doc.txt: {str(e)}")
        traceback.print_exc()
        return False

@router.get("/{case_id}")
async def get_case_details(
    case_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Get case details for a specific case ID.
    """
    print(f"[CASE_DETAILS] 📝 Processing case details request for case {case_id}")
    
    # Extract token and authenticate the user
    try:
        token = credentials.credentials  # This is the raw JWT
        print(f"[DEBUG] Extracted JWT: {token}")
        
        print(f"[CASE_DETAILS] 🔐 Authenticating user...")
        user_response = await get_user_from_token(token)
        if not user_response["success"]:
            error_message = user_response.get("error", "Authentication required")
            print(f"[CASE_DETAILS] ❌ Authentication failed: {error_message}")
            raise HTTPException(status_code=401, detail=error_message)
        
        user_id = user_response["user"]["id"]
        print(f"[CASE_DETAILS] ✅ User authenticated successfully. User ID: {user_id}")
        
        try:
            case_base_path = os.path.join('case-data', f'case{case_id}')
            print(f"\nAccessing case directory: {case_base_path}")
            
            # Try to update the case document
            update_result = update_case_doc_from_uploads(case_id)
            if update_result:
                print(f"Case document was successfully updated from @uploads folder")
            else:
                print(f"No updates made to case document or update failed")

            # Define all required file paths with correct structure
            data_file_path = os.path.join(case_base_path, 'test_exam_data.json')
            cover_file_path = os.path.join(case_base_path, 'case_cover.json')
            persona_file_path = os.path.join(case_base_path, 'patient_prompts', 'patient_persona.txt')
            history_context_path = os.path.join(case_base_path, 'history_context.json')
            treatment_context_path = os.path.join(case_base_path, 'treatment_context.json')
            clinical_findings_context_path = os.path.join(case_base_path, 'clinical_findings_context.json')
            diagnosis_context_path = os.path.join(case_base_path, 'diagnosis_context.json')
            
            print(f"Looking for files:")
            print(f"Data file: {data_file_path} (exists: {os.path.exists(data_file_path)})")
            print(f"Cover file: {cover_file_path} (exists: {os.path.exists(cover_file_path)})")
            print(f"Persona file: {persona_file_path} (exists: {os.path.exists(persona_file_path)})")
            print(f"History context file: {history_context_path} (exists: {os.path.exists(history_context_path)})")
            print(f"Treatment context file: {treatment_context_path} (exists: {os.path.exists(treatment_context_path)})")
            print(f"Clinical findings context file: {clinical_findings_context_path} (exists: {os.path.exists(clinical_findings_context_path)})")
            print(f"Diagnosis context file: {diagnosis_context_path} (exists: {os.path.exists(diagnosis_context_path)})")
            
            # Check if required files exist
            if not os.path.exists(data_file_path):
                print(f"ERROR: Case exam data not found at: {data_file_path}")
                raise HTTPException(status_code=404, detail="Case exam data not found")
            if not os.path.exists(cover_file_path):
                print(f"ERROR: Case cover data not found at: {cover_file_path}")
                raise HTTPException(status_code=404, detail="Case cover data not found")
            
            # Load the case exam data
            print("Loading exam data...")
            with open(data_file_path, 'r') as file:
                exam_data = json.load(file)
            
            # Load the case cover data
            print("Loading cover data...")
            with open(cover_file_path, 'r') as cover_file:
                case_cover_data = json.load(cover_file)
                
            # Load patient persona from the correct path
            patient_persona = {"content": ""}  # Initialize with empty content
            if os.path.exists(persona_file_path):
                print("Loading patient persona...")
                with open(persona_file_path, 'r', encoding='utf-8') as persona_file:
                    persona_text = persona_file.read().strip()
                    patient_persona["content"] = persona_text
                    print(f"Persona content length: {len(persona_text)} characters")
            else:
                print(f"WARNING: Patient persona not found at: {persona_file_path}")
                
            # Load history context data if available
            history_context = {"content": {}}  # Initialize with empty content object
            if os.path.exists(history_context_path):
                print("Loading history context...")
                with open(history_context_path, 'r', encoding='utf-8') as history_file:
                    history_data = json.load(history_file)
                    history_context["content"] = history_data
                    print(f"History context loaded successfully")
            else:
                print(f"WARNING: History context not found at: {history_context_path}")
                
            # Load treatment context data if available
            treatment_context = {"content": {}}  # Initialize with empty content object
            if os.path.exists(treatment_context_path):
                print("Loading treatment context...")
                with open(treatment_context_path, 'r', encoding='utf-8') as treatment_file:
                    treatment_data = json.load(treatment_file)
                    treatment_context["content"] = treatment_data
                    print(f"Treatment context loaded successfully")
            else:
                print(f"WARNING: Treatment context not found at: {treatment_context_path}")
                
            # Load clinical findings context data if available
            clinical_findings_context = {"content": {}}  # Initialize with empty content object
            if os.path.exists(clinical_findings_context_path):
                print("Loading clinical findings context...")
                with open(clinical_findings_context_path, 'r', encoding='utf-8') as findings_file:
                    findings_data = json.load(findings_file)
                    clinical_findings_context["content"] = findings_data
                    print(f"Clinical findings context loaded successfully")
            else:
                print(f"WARNING: Clinical findings context not found at: {clinical_findings_context_path}")
                
            # Load diagnosis context data if available
            diagnosis_context = {"content": {}}  # Initialize with empty content object
            if os.path.exists(diagnosis_context_path):
                print("Loading diagnosis context...")
                with open(diagnosis_context_path, 'r', encoding='utf-8') as diagnosis_file:
                    diagnosis_data = json.load(diagnosis_file)
                    diagnosis_context["content"] = diagnosis_data
                    print(f"Diagnosis context loaded successfully")
            else:
                print(f"WARNING: Diagnosis context not found at: {diagnosis_context_path}")

            return {
                "content": {
                    "case_cover": case_cover_data if case_cover_data != {} else None,
                    "test_data": exam_data if exam_data != {} else None,
                    "patient_persona": patient_persona if patient_persona != {} else None,
                    "history_context": history_context if history_context['content'] != {} else None,
                    "treatment_context": treatment_context if treatment_context['content'] != {} else None,
                    "clinical_findings_context": clinical_findings_context if clinical_findings_context['content'] != {} else None,
                    "diagnosis_context": diagnosis_context if diagnosis_context['content'] != {} else None
                }
            }

        except json.JSONDecodeError as e:
            print(f"ERROR: JSON decode error: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error decoding JSON data: {str(e)}"
            )
        except Exception as e:
            print(f"ERROR: Unexpected error: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error retrieving case data: {str(e)}"
            )
            
    except HTTPException as auth_error:
        print(f"[CASE_DETAILS] ❌ HTTP exception during authentication: {str(auth_error)}")
        raise auth_error
    except Exception as auth_error:
        print(f"[CASE_DETAILS] ❌ Unexpected error during authentication: {str(auth_error)}")
        raise HTTPException(status_code=401, detail="Authentication failed") 
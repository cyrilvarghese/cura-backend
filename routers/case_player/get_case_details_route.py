from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any
import json
import os
import traceback
import dateutil.parser

from routers.curriculum import get_db_connection

case_details_router = APIRouter()

class CaseDetailsResponse(BaseModel):
    content: Dict[str, Any]

@case_details_router.get("/case-details/{case_id}", response_model=CaseDetailsResponse)
async def get_case_details(case_id: str):
    case_base_path = os.path.join('case-data', f'case{case_id}')
    print(f"\nAccessing case directory: {case_base_path}")
    
    # Define all required file paths with correct structure
    data_file_path = os.path.join(case_base_path, 'test_exam_data.json')
    cover_file_path = os.path.join(case_base_path, 'case_cover.json')
    persona_file_path = os.path.join(case_base_path, 'patient_prompts', 'patient_persona.txt')
    
    print(f"Looking for files:")
    print(f"Data file: {data_file_path} (exists: {os.path.exists(data_file_path)})")
    print(f"Cover file: {cover_file_path} (exists: {os.path.exists(cover_file_path)})")
    print(f"Persona file: {persona_file_path} (exists: {os.path.exists(persona_file_path)})")
    
    # Check if required files exist
    if not os.path.exists(data_file_path):
        print(f"ERROR: Case exam data not found at: {data_file_path}")
        raise HTTPException(status_code=404, detail="Case exam data not found")
    if not os.path.exists(cover_file_path):
        print(f"ERROR: Case cover data not found at: {cover_file_path}")
        raise HTTPException(status_code=404, detail="Case cover data not found")
    
    try:
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

        # # Get Google Doc link from Supabase
        # from auth.auth_api import get_client
        # supabase = get_client()
        
        # print(f"Querying Supabase for document with title: {case_cover_data['case_name']}")
        # supabase_result = supabase.table("documents")\
        #     .select("google_doc_id, google_doc_link, last_modified_time")\
        #     .eq("title", case_cover_data['case_name'])\
        #     .execute()
        
        # doc_has_changed = False
        # if supabase_result.data and len(supabase_result.data) > 0:
        #     doc_data = supabase_result.data[0]
        #     google_doc_id = doc_data.get('google_doc_id')
        #     google_doc_link = doc_data.get('google_doc_link')
        #     stored_modified_time = doc_data.get('last_modified_time')
            
        #     print(f"Stored: {stored_modified_time}")
            
        #     case_cover_data['google_doc_link'] = google_doc_link
            
        #     # Check if the document has been modified
        #     if google_doc_id:
        #         try:
        #             # Import here to avoid circular imports
        #             from utils.google_docs import GoogleDocsManager
                    
        #             # Get the document details from Google Drive
        #             gdocs = GoogleDocsManager()
        #             doc_details = gdocs.get_doc_details(google_doc_id)
                    
        #             if doc_details:
        #                 current_modified_time = doc_details.get('modifiedTime')
        #                 print(f"Current: {current_modified_time}")
                        
        #                 # If stored_modified_time is None or empty, update it without marking as changed
        #                 if not stored_modified_time:
        #                     try:
        #                         supabase.table("documents")\
        #                             .update({"last_modified_time": current_modified_time})\
        #                             .eq("google_doc_id", google_doc_id)\
        #                             .execute()
        #                         doc_has_changed = False
        #                         print(f"Updated null last_modified_time to: {current_modified_time}")
        #                     except Exception as update_error:
        #                         print(f"Error updating last_modified_time: {str(update_error)}")
        #                 # Otherwise just check if it's different but don't update
        #                 else:
        #                     # Normalize time formats for comparison
        #                     try:
        #                         # Parse both times to datetime objects and compare
        #                         stored_dt = dateutil.parser.parse(stored_modified_time)
        #                         current_dt = dateutil.parser.parse(current_modified_time)
                                
        #                         print(f"Parsed stored time: {stored_dt.isoformat()}")
        #                         print(f"Parsed current time: {current_dt.isoformat()}")
                                
        #                         if stored_dt != current_dt:
        #                             doc_has_changed = True
        #                             print(f"Document has changed! Times are different after normalization")
        #                         else:
        #                             print(f"Document has NOT changed - times match after normalization")
        #                     except Exception as parse_error:
        #                         print(f"Error parsing time formats: {str(parse_error)}")
        #                         # Fall back to string comparison if parsing fails
        #                         if current_modified_time != stored_modified_time:
        #                             doc_has_changed = True
        #                             print(f"Document has changed! String comparison of times")
        #                         else:
        #                             print(f"Document has NOT changed - string comparison match")
        #         except Exception as e:
        #             print(f"WARNING: Could not check document modification: {str(e)}")
        #     else:
        #         case_cover_data['google_doc_link'] = None
        #         print(f"No document found in Supabase with title: {case_cover_data['case_name']}")
        # else:
        #     case_cover_data['google_doc_link'] = None
        
        # # Add the change status to the response
        # case_cover_data['doc_has_changed'] = doc_has_changed
        # print(f"Final doc_has_changed status: {doc_has_changed}")

        return {
            "content": {
                "case_cover": case_cover_data,
                "test_data": exam_data,
                "patient_persona": patient_persona
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
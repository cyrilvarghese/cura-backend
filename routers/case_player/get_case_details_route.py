from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional
import json
import os

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
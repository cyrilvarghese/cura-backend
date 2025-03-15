from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List
import json
import os
from pathlib import Path
from datetime import datetime

case_router = APIRouter()

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

class CaseCoverUpdate(BaseModel):
    published: bool
    department: str

@case_router.get("/cases", response_model=List[CaseInfo])
async def list_cases():
    """List all available published cases by reading case_cover.json files"""
    cases = []
    case_data_dir = Path("case-data")
    
    # Iterate through all case folders
    for case_dir in sorted(case_data_dir.glob("case*")):
        cover_file = case_dir / "case_cover.json"
        if cover_file.exists():
            try:
                with open(cover_file, "r") as f:
                    cover_data = json.load(f)
                    # Only include published cases
                    if cover_data.get("published", False):
                        case_info = CaseInfo(
                            case_id=cover_data.get("case_id", 0),  # Default to 0 if not specified
                            case_name=cover_data["case_name"],
                            title=cover_data.get("title"),
                            quote=cover_data.get("quote"),
                            image_url=cover_data.get("image_url"),
                            last_updated=cover_data.get("last_updated"),
                            differential_diagnosis=cover_data.get("differential_diagnosis"),
                            department=cover_data.get("department"),
                            published=cover_data.get("published")
                        )
                        cases.append(case_info)
            except (json.JSONDecodeError, KeyError) as e:
                print(f"Error reading {cover_file}: {e}")
                continue
    
    # Sort cases by case_id
    cases.sort(key=lambda x: x.case_id)
    return cases

@case_router.get("/cases/{case_id}", response_model=CaseData)
async def get_case_data(case_id: str):
    # Define paths for the case data and case cover
    data_file_path = os.path.join('case-data', f'case{case_id}', 'test_exam_data.json')
    cover_file_path = os.path.join('case-data', f'case{case_id}', 'case_cover.json')
    
    # Check if the case data file exists
    if not os.path.exists(data_file_path):
        raise HTTPException(status_code=404, detail="Case exam data not found")
    
    # Load the case data
    with open(data_file_path, 'r') as file:
        data = json.load(file)
    
    # Check if the case cover file exists
    if not os.path.exists(cover_file_path):
        raise HTTPException(status_code=404, detail="Case cover data not found")
    
    # Load the case cover data
    with open(cover_file_path, 'r') as cover_file:
        case_cover_data = json.load(cover_file)

    return {
        "content": {
            "physical_exam": data.get("physical_exam", {}),
            "lab_test": data.get("lab_test", {}),
            "case_cover": case_cover_data  # Include case cover data in the response
        }
    }

@case_router.post("/cases/{case_id}/cover", response_model=dict)
async def update_case_cover(case_id: str, update_data: CaseCoverUpdate):
    """Update published status and department in the case cover file"""
    try:
        cover_file_path = os.path.join('case-data', f'case{case_id}', 'case_cover.json')
        
        # Check if the case cover file exists
        if not os.path.exists(cover_file_path):
            raise HTTPException(status_code=404, detail="Case cover data not found")
        
        # Read existing case cover data
        with open(cover_file_path, 'r') as f:
            case_cover_data = json.load(f)
        
        # Update only published and department fields
        case_cover_data["published"] = update_data.published
        case_cover_data["department"] = update_data.department
        
        # Update last_updated timestamp
        case_cover_data["last_updated"] = datetime.now().isoformat()
        
        # Write the updated data back to the file
        with open(cover_file_path, 'w') as f:
            json.dump(case_cover_data, f, indent=4)
            
        return {
            "status": "success",
            "message": "Case cover updated successfully",
            "case_id": case_id
        }

    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Error decoding JSON from case cover file: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error updating case cover: {str(e)}"
        ) 
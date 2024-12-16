from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any
import json
import os
# get the case data from the case-data folder for the case player to use

case_router = APIRouter()

class CaseData(BaseModel):
    content: Dict[str, Any]

@case_router.get("/cases/{case_id}", response_model=CaseData)
async def get_case_data(case_id: str):
    # Define paths for the case data and case cover
    data_file_path = os.path.join('case-data', f'case{case_id}', 'test_exam_data.json')
    cover_file_path = os.path.join('case-data', f'case{case_id}', 'case_cover.json')
    
    # Check if the case data file exists
    if not os.path.exists(data_file_path):
        raise HTTPException(status_code=404, detail="Case not found")
    
    # Load the case data
    with open(data_file_path, 'r') as file:
        data = json.load(file)
    
    # Check if the case cover file exists
    if not os.path.exists(cover_file_path):
        raise HTTPException(status_code=404, detail="Case cover not found")
    
    # Load the case cover data
    with open(cover_file_path, 'r') as cover_file:
        case_cover_data = json.load(cover_file)

    return {
        "content": {
            "physical_exam": data.get("physical_exam", {}),
            "lab_test": data.get("lab_test", {}),
            "cover_message": data.get("cover_message", {}),
            "case_cover": case_cover_data  # Include case cover data in the response
        }
    } 
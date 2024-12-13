from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any
import json
import os

case_router = APIRouter()

class CaseData(BaseModel):
    content: Dict[str, Any]

@case_router.get("/cases/{case_id}", response_model=CaseData)
async def get_case_data(case_id: str):
    file_path = os.path.join('case-data', f'case{case_id}', 'test_exam_data.json')
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Case not found")
    
    with open(file_path, 'r') as file:
        data = json.load(file)
    
    return {
        "content": {
            "physical_exam": data.get("physical_exam", {}),
            "lab_test": data.get("lab_test", {}),
            "cover_message": data.get("cover_message", {}),
        }
    } 
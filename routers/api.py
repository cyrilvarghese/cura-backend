from fastapi import APIRouter
from .users import user_router
from typing import List
from pydantic import BaseModel
from datetime import datetime
from routers.case_creator.create_patient_persona import router as create_patient_persona_router
from routers.case_creator.create_exam_test_data import router as create_exam_test_data_router
from routers.case_creator.create_cover_image import router as create_cover_image_router
from routers.case_creator.create_diff_diagnosis import router as create_diff_diagnosis_router
from routers.case_player.get_student_feedback import feedback_router
from routers.case_player.patient_simulation import router as patient_simulation_router
from routers.case_player.get_case_data_routes import case_router
from routers.case_creator.upload_test_image import router as upload_test_image_router
import os
import json
from pathlib import Path
from routers.image_search import router as image_search_router

api_router = APIRouter()

class StudentAction(BaseModel):
    content: str
    step: str
    timestamp: datetime

class CaseInfo(BaseModel):
    case_id: int
    case_name: str
    title: str | None = None
    quote: str | None = None
    image_url: str | None = None

# Add your routes here
@api_router.get("/")
async def root():
    return {"message": "Hello World new"}

# Include the other routers
api_router.include_router(user_router)
api_router.include_router(feedback_router)
api_router.include_router(case_router)
api_router.include_router(patient_simulation_router) 
api_router.include_router(create_patient_persona_router) 
api_router.include_router(create_exam_test_data_router)
api_router.include_router(create_cover_image_router)
api_router.include_router(create_diff_diagnosis_router)
api_router.include_router(upload_test_image_router)     
api_router.include_router(image_search_router)

@api_router.get("/cases", response_model=List[CaseInfo])
async def list_cases():
    """List all available cases by reading case_cover.json files"""
    cases = []
    case_data_dir = Path("case-data")
    
    # Iterate through all case folders
    for case_dir in sorted(case_data_dir.glob("case*")):
        cover_file = case_dir / "case_cover.json"
        if cover_file.exists():
            try:
                with open(cover_file, "r") as f:
                    cover_data = json.load(f)
                    # Convert to CaseInfo model
                    case_info = CaseInfo(
                        case_id=cover_data.get("case_id", 0),  # Default to 0 if not specified
                        case_name=cover_data["case_name"],
                        title=cover_data.get("title"),
                        quote=cover_data.get("quote"),
                        image_url=cover_data.get("image_url")
                    )
                    cases.append(case_info)
            except (json.JSONDecodeError, KeyError) as e:
                print(f"Error reading {cover_file}: {e}")
                continue
    
    # Sort cases by case_id
    cases.sort(key=lambda x: x.case_id)
    return cases

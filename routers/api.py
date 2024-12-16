from fastapi import APIRouter
from .users import user_router
from typing import List
from pydantic import BaseModel
from datetime import datetime
from routers.case_creator.create_patient_persona import router as create_patient_persona_router
from routers.case_creator.create_exam_test_data import router as create_exam_test_data_router
from routers.case_creator.create_cover_image import router as create_cover_image_router
from routers.case_player.get_student_feedback import feedback_router
from routers.case_player.patient_simulation import router as patient_simulation_router
from routers.case_player.get_case_data_routes import case_router
api_router = APIRouter()

class StudentAction(BaseModel):
    content: str
    step: str
    timestamp: datetime

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

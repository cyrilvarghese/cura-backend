from fastapi import APIRouter, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from .users import user_router
from typing import List
from pydantic import BaseModel
from routers.upload_resource import router as upload_resource_router
from routers.google_docs_router import router as google_docs_router
from datetime import datetime
from routers.case_creator.create_patient_persona import router as create_patient_persona_router
from routers.case_creator.create_exam_test_data import router as create_exam_test_data_router
from routers.case_creator.create_history_context import router as create_history_context_router
from routers.case_creator.create_treatment_context import router as create_treatment_context_router
from routers.case_creator.create_clinical_findings_context import router as create_clinical_findings_context_router
from routers.case_creator.create_diagnosis_context import router as create_diagnosis_context_router
from routers.case_creator.create_cover_image import router as create_cover_image_router
from routers.case_creator.create_diff_diagnosis import router as create_diff_diagnosis_router
from routers.case_player.patient_simulation import router as patient_simulation_router
from routers.case_player.get_case_data_routes import case_router
from routers.case_creator.upload_test_image import router as upload_test_image_router
from .curriculum import router as curriculum_router
import os
import json
from pathlib import Path
from routers.image_search import router as image_search_router
from routers.intelligent_image_search import router as intelligent_image_search_router
from routers.case_creator.update_test_table import router as update_test_table_router
from routers.case_player.get_case_details_route import router as case_details_router    
from routers.case_creator.evaluate_student_questions import router as evaluate_student_questions_router
from routers.relevant_info_feedback import router as relevant_info_feedback_router
from routers.case_creator.update_test_comment import router as update_test_comment_router
from routers.case_creator.update_case_quote import router as update_case_quote_router
from routers.case_player.treatment_feedback_gemini import router as treatment_feedback_gemini_router
from routers.case_player.history_feedback_gemini import router as history_feedback_gemini_router
from routers.case_player.history_feedback_langchain import router as history_feedback_langchain_router
from routers.case_player.test_validator import router as test_validator_router
from routers.case_player.history_match import router as history_match_router
from routers.feature_requests.feature_request_routes import feature_router
from routers.record_clinical_findings import router as clinical_findings_router
from routers.record_diagnosis import router as diagnosis_router
from routers.final_diagnosis import router as final_diagnosis_router
from routers.record_pre_treatment_monitoring import router as treatment_monitoring_router
from routers.record_treatment_plan import router as treatment_plan_router
from routers.osce_generator import router as osce_generator_router
from routers.case_player.final_osce_feedback import router as final_osce_feedback_router
from routers.record_osce_score import router as osce_score_router
from routers.student_performance_api import performance_router
from routers.case_player.diagnosis_feedback_v2 import router as diagnosis_feedback_v2_router
from routers.case_player.treatment_final_feedback import router as treatment_final_feedback_router
from auth.router import router as auth_router
from fastapi import HTTPException
from routers.case_creator.edit_physical_exam import router as edit_physical_exam_router
from routers.case_creator.edit_lab_test import router as edit_lab_test_router

api_router = APIRouter()

# Define the security scheme
security = HTTPBearer()

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
api_router.include_router(case_router)
api_router.include_router(patient_simulation_router) 
api_router.include_router(create_patient_persona_router) 
api_router.include_router(create_exam_test_data_router)
api_router.include_router(create_history_context_router)
api_router.include_router(create_treatment_context_router)
api_router.include_router(create_clinical_findings_context_router)
api_router.include_router(create_diagnosis_context_router)
api_router.include_router(create_cover_image_router)
api_router.include_router(create_diff_diagnosis_router)
api_router.include_router(upload_test_image_router)     
api_router.include_router(image_search_router)
api_router.include_router(intelligent_image_search_router)
api_router.include_router(curriculum_router)
api_router.include_router(upload_resource_router)
api_router.include_router(update_test_table_router)
api_router.include_router(update_test_comment_router)
api_router.include_router(update_case_quote_router)
api_router.include_router(google_docs_router)
api_router.include_router(case_details_router)
api_router.include_router(evaluate_student_questions_router)
api_router.include_router(relevant_info_feedback_router)
api_router.include_router(treatment_feedback_gemini_router)
api_router.include_router(history_feedback_gemini_router)
api_router.include_router(history_feedback_langchain_router)
 
api_router.include_router(test_validator_router)
api_router.include_router(history_match_router)
api_router.include_router(feature_router)
api_router.include_router(clinical_findings_router)
api_router.include_router(diagnosis_router)
api_router.include_router(final_diagnosis_router)
api_router.include_router(treatment_monitoring_router)
api_router.include_router(treatment_plan_router)
api_router.include_router(osce_generator_router)
api_router.include_router(final_osce_feedback_router)
api_router.include_router(osce_score_router)
api_router.include_router(performance_router)
api_router.include_router(diagnosis_feedback_v2_router)
api_router.include_router(treatment_final_feedback_router)
api_router.include_router(auth_router)
api_router.include_router(edit_physical_exam_router)
api_router.include_router(edit_lab_test_router)

 
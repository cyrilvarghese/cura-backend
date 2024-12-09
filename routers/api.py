from fastapi import APIRouter
from .users import user_router
from .products import product_router
from .student_feedback import feedback_router
from .cases import case_router
from typing import List
from pydantic import BaseModel
from datetime import datetime

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
api_router.include_router(product_router)
api_router.include_router(feedback_router)
api_router.include_router(case_router) 
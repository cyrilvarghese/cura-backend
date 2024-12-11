from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
from routers.api import api_router
from routers.langchain_routes import router as langchain_router
from routers.langchain_simple import router as translate_router
from routers.patient_simulation import router as patient_router
from routers.markdown import markdown_router
from routers.create_patient_persona import router as create_data_router        
from routers.create_exam_test_data import router as create_exam_test_data_router

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create static directory if it doesn't exist
static_dir = "static"
if not os.path.exists(static_dir):
    os.makedirs(static_dir)

# Mount the static files directory
try:
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
except RuntimeError as e:
    print(f"Error mounting static files: {e}")

# Include routers
app.include_router(api_router)
app.include_router(langchain_router)
app.include_router(translate_router) 
app.include_router(patient_router) 
app.include_router(markdown_router) 
app.include_router(create_data_router) 
app.include_router(create_exam_test_data_router)

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
import os
from routers.api import api_router
from auth.router import router as auth_router
from routers import google_docs_router
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = FastAPI()

# Define allowed origins - use specific origins in production for security
origins = [
    "http://localhost",
    "http://localhost:3000",  # Common React development port
    "http://localhost:5173",  # Common Vite development port
    "http://localhost:5174",  # Another Vite port
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
    "http://127.0.0.1:3000",
    # Add your production URLs here
    "*"  # Allow all origins - remove this in production
]

# Add CORS middleware with explicit configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=600  # Cache preflight requests for 10 minutes
)

# Create static directory if it doesn't exist
static_dir = "static"
if not os.path.exists(static_dir):
    os.makedirs(static_dir)

# Set up case-data directory
CASE_DATA_DIR = Path("case-data").absolute()
if not CASE_DATA_DIR.exists():
    CASE_DATA_DIR.mkdir(parents=True)

# Create uploads directory if it doesn't exist
UPLOAD_DIR = os.getenv("UPLOADS_DIR", "case-data/uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Mount the static files directories
try:
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    app.mount("/case-files", StaticFiles(directory=str(CASE_DATA_DIR)), name="case-data")
    app.mount("/case-images", StaticFiles(directory="case-data"), name="case-images")
    app.mount("/files", StaticFiles(directory=UPLOAD_DIR), name="files")
except RuntimeError as e:
    print(f"Error mounting static files: {e}")

# File server endpoints
@app.get("/files")
async def list_files():
    """List all files in the case-data directory"""
    try:
        files = os.listdir(CASE_DATA_DIR)
        return {"files": files}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/files/{filename}")
async def download_file(filename: str):
    """Download a specific file from case-data directory"""
    file_path = CASE_DATA_DIR / filename
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File {filename} not found")
        
    try:
        return FileResponse(
            path=file_path,
            filename=filename,
            media_type="application/octet-stream"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Include routers
app.include_router(api_router)
app.include_router(auth_router)
app.include_router(google_docs_router.router, prefix="/api", tags=["Google Docs"])

# Root endpoint
@app.get("/")
async def root():
    return {"message": "API is running"}

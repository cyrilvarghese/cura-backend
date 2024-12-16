from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
from routers.api import api_router

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

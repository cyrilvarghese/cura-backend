from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import os
from pathlib import Path
import json

case_router = APIRouter(
    prefix="/cases",
    tags=["cases"]
)

class PatientPersonaRequest(BaseModel):
    persona_prompt: str

async def ensure_directory_exists(directory: Path) -> None:
    """Ensure that the specified directory exists, creating it if necessary."""
    if not directory.exists():
        try:
            os.makedirs(directory)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to create directory: {str(e)}"
            )

async def write_to_file(file_path: Path, content: str) -> None:
    """Write the specified content to a file."""
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to write file: {str(e)}"
        )

 
async def create_patient_persona(case_id: str, request: PatientPersonaRequest):
    try:
        # Create the directory path
        base_path = Path("case-data")
        case_dir = base_path / f"case{case_id}" / "patient_prompts"
        file_path = case_dir / "patient_persona.txt"

        # Ensure base case-data directory exists
        await ensure_directory_exists(base_path)

        # Create case and patient_prompts directories
        await ensure_directory_exists(case_dir)

        # Write the persona prompt content to the file
        await write_to_file(file_path, request.persona_prompt)

        return {
            "success": True,
            "message": "Patient persona file created successfully",
            "file_path": str(file_path)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create patient persona file: {str(e)}"
        )
 
async def create_examination_data(case_id: str, data: dict) -> dict:
    """Create examination data and save it to a specified file."""
    try:
        # Create the directory path
        base_path = Path("case-data")
        exam_dir = base_path / f"case{case_id}" 
        file_path = exam_dir / "test_exam_data.json"

        # Ensure base case-data directory exists
        await ensure_directory_exists(base_path)

        # Create test_exam_data directory
        await ensure_directory_exists(exam_dir)

        # Write the examination data content to the file
        await write_to_file(file_path, json.dumps(data, indent=4))  # Save data as JSON

        return {
            "success": True,
            "message": "Examination data file created successfully",
            "file_path": str(file_path)
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create examination data file: {str(e)}"
        )
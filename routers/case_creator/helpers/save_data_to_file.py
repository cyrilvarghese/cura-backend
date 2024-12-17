from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import os
from pathlib import Path
import json
from datetime import datetime

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

 
async def save_patient_persona(case_id: str, request: PatientPersonaRequest):
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
 
async def save_examination_data(case_id: str, data: dict) -> dict:
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

async def save_differential_diagnosis(case_id: int, data: dict) -> dict:
    """Update the differentials in the case cover JSON file."""
    try:
        case_folder = f"case-data/case{case_id}"
        case_cover_path = os.path.join(case_folder, "case_cover.json")
        
        # Read the existing case cover data
        with open(case_cover_path, 'r') as json_file:
            case_cover_data = json.load(json_file)
        
        # Update the differentials
        case_cover_data["differentials"] = data
        case_cover_data["last_updated"] = datetime.now().isoformat()
        
        # Write the updated JSON data back to the file
        with open(case_cover_path, 'w') as json_file:
            json.dump(case_cover_data, json_file, indent=4)
            
        return {
            "status": "success",
            "file_path": case_cover_path,
            "message": "Differential diagnoses updated in case cover successfully",
            "case_id": case_id
        }
        
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Case cover file not found for case {case_id}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error updating differential diagnoses in case cover: {str(e)}"
        )
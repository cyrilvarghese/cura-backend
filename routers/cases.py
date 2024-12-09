from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import os
from pathlib import Path

case_router = APIRouter(
    prefix="/cases",
    tags=["cases"]
)

class PatientPersonaRequest(BaseModel):
    persona_prompt: str

@case_router.post("/{case_id}/patient-prompts")
async def create_patient_persona(case_id: str, request: PatientPersonaRequest):
    try:
        # Create the directory path
        base_path = Path("case-data")
        case_dir = base_path / f"case{case_id}" / "patient_prompts"
        file_path = case_dir / "patient_persona.txt"

        # Ensure base case-data directory exists
        if not base_path.exists():
            try:
                os.makedirs(base_path)
            except Exception as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to create base directory: {str(e)}"
                )

        # Create case and patient_prompts directories
        try:
            os.makedirs(case_dir, exist_ok=True)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to create case directories: {str(e)}"
            )

        # Write the persona prompt content to the file
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(request.persona_prompt)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to write file: {str(e)}"
            )

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
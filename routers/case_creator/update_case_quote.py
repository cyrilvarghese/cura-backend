from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import os
import json
from datetime import datetime
from pathlib import Path
from typing import Any

router = APIRouter(
    prefix="/case_quote",
    tags=["create-data"]
)

class UpdateQuoteRequest(BaseModel):
    case_id: Any
    quote_text: str

@router.post("/update")
async def update_case_quote(request: UpdateQuoteRequest):
    """
    Update the quote field in the case_cover.json file for the specified case ID.
    
    Parameters:
    - case_id: The ID of the case to update
    - quote_text: The new quote text to be saved
    
    Returns:
    - A JSON object containing the status, file path, and message
    """
    try:
        # Construct the case folder path
        case_folder = f"case-data/case{request.case_id}"
        case_cover_path = os.path.join(case_folder, "case_cover.json")
        
        # Check if the file exists
        if not os.path.exists(case_cover_path):
            raise HTTPException(
                status_code=404,
                detail=f"Case cover file not found for case {request.case_id}"
            )
        
        # Read the existing case cover data
        with open(case_cover_path, 'r') as json_file:
            case_cover_data = json.load(json_file)
        
        # Update the quote field - actually the title
        case_cover_data["title"] = request.quote_text
        
        # Update the last_updated timestamp
        case_cover_data["last_updated"] = datetime.now().isoformat()
        
        # Write the updated JSON data back to the file
        with open(case_cover_path, 'w') as json_file:
            json.dump(case_cover_data, json_file, indent=4)
            
        return {
            "status": "success",
            "file_path": case_cover_path,
            "message": f"Quote updated successfully for case {request.case_id}",
            "case_id": request.case_id
        }
        
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Case cover file not found for case {request.case_id}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error updating quote in case cover: {str(e)}"
        ) 
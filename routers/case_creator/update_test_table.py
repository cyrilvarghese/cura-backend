from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Union
import json
import os

router = APIRouter(
    prefix="/test-table",
    tags=["create-data"]
)

class TableRow(BaseModel):
    values: List[str]

class TableUpdateRequest(BaseModel):
    case_id: str
    test_name: str
    test_type: str  # "physical_exam" or "lab_test"
    rows: List[TableRow]

@router.put("/update")
async def update_test_table(request: TableUpdateRequest):
    """
    Update table values in test_exam_data.json for a specific test
    
    Args:
        request: TableUpdateRequest containing case_id, test_name, test_type, and new row values
    """
    try:
        json_path = f"case-data/case{request.case_id}/test_exam_data.json"
        
        if not os.path.exists(json_path):
            raise HTTPException(
                status_code=404,
                detail=f"test_exam_data.json not found for case {request.case_id}"
            )

        with open(json_path, 'r') as file:
            data = json.load(file)

        # Get the test category
        test_category = data.get(request.test_type)
        if not test_category:
            raise HTTPException(
                status_code=404,
                detail=f"Test type {request.test_type} not found"
            )

        # Get the specific test
        test_data = test_category.get(request.test_name)
        if not test_data:
            raise HTTPException(
                status_code=404,
                detail=f"Test {request.test_name} not found"
            )

        # Check if the test has table-type results/findings
        results_key = "findings" if request.test_type == "physical_exam" else "results"
        if not test_data.get(results_key, {}).get("type") == "table":
            raise HTTPException(
                status_code=400,
                detail=f"Test {request.test_name} does not have table-type {results_key}"
            )

        # Update the table rows while preserving headers
        table_content = test_data[results_key]["content"]
        headers = table_content["headers"]
        
        # Validate row lengths match headers
        for row in request.rows:
            if len(row.values) != len(headers):
                raise HTTPException(
                    status_code=400,
                    detail=f"Row length ({len(row.values)}) does not match headers length ({len(headers)})"
                )

        # Update the rows
        table_content["rows"] = [row.values for row in request.rows]

        # Save the updated JSON
        with open(json_path, 'w') as file:
            json.dump(data, file, indent=4)

        return {
            "message": "Table updated successfully",
            "test_name": request.test_name,
            "updated_rows": len(request.rows)
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred: {str(e)}"
        ) 
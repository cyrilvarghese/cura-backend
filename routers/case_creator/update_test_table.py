from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Union, Any
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
        request: TableUpdateRequest containing case_id, test_name, test_type, and rows to update
    """
    try:
        print(f"Received update request for case {request.case_id}, test {request.test_name}")
        print(f"Rows to update: {[row.values for row in request.rows]}")
        
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

        # Get the table content
        table_content = test_data[results_key]["content"]
        headers = table_content["headers"]
        existing_rows = table_content.get("rows", [])
        
        print(f"Existing rows before update: {existing_rows}")
        
        # Track which rows were updated
        updated_rows = []
        
        # Process each row in the request
        for new_row in request.rows:
            # Validate row length
            if len(new_row.values) != len(headers):
                raise HTTPException(
                    status_code=400,
                    detail=f"Row length ({len(new_row.values)}) does not match headers length ({len(headers)})"
                )
            
            # Try to find a matching row by the first column (usually the test name/parameter)
            row_identifier = new_row.values[0]
            found = False
            
            # Look for an existing row with the same identifier
            for i, existing_row in enumerate(existing_rows):
                if existing_row and len(existing_row) > 0 and existing_row[0] == row_identifier:
                    # Found a match - update this row
                    print(f"Updating row with identifier '{row_identifier}'")
                    existing_rows[i] = new_row.values
                    updated_rows.append(row_identifier)
                    found = True
                    break
            
            # If no matching row was found, append the new row
            if not found:
                print(f"Adding new row with identifier '{row_identifier}'")
                existing_rows.append(new_row.values)
                updated_rows.append(row_identifier)
        
        print(f"Rows after update: {existing_rows}")
        
        # Update the rows in the table content
        table_content["rows"] = existing_rows

        # Save the updated JSON
        with open(json_path, 'w') as file:
            json.dump(data, file, indent=4)

        return {
            "message": "Table updated successfully",
            "test_name": request.test_name,
            "updated_rows": updated_rows,
            "total_rows": len(existing_rows)
        }
    except Exception as e:
        print(f"Error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred: {str(e)}"
        ) 
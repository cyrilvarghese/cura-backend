from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import json
import os
from datetime import datetime

router = APIRouter(
    prefix="/test-comment",
    tags=["create-data"]
)

class CommentUpdateRequest(BaseModel):
    case_id: str
    test_type: str  # "physical_exam" or "lab_test"
    test_name: str
    comment: str

class CommentDeleteRequest(BaseModel):
    case_id: str
    test_type: str
    test_name: str
    comment_index: int  # Index of the comment to remove

@router.put("/add")
async def add_test_comment(request: CommentUpdateRequest):
    """
    Add a comment to the test data in test_exam_data.json
    
    Args:
        request: CommentUpdateRequest containing case_id, test_type, test_name, and comment
    """
    try:
        print(f"[{datetime.now()}] 🔍 Received comment update request for case {request.case_id}")
        print(f"[DEBUG] Request details: test_type={request.test_type}, test_name={request.test_name}")
        print(f"[DEBUG] Comment content: {request.comment[:50]}..." if len(request.comment) > 50 else f"[DEBUG] Comment content: {request.comment}")
        
        json_path = f"case-data/case{request.case_id}/test_exam_data.json"
        print(f"[DEBUG] Looking for file at: {json_path}")
        
        if not os.path.exists(json_path):
            print(f"[{datetime.now()}] ❌ File not found: {json_path}")
            raise HTTPException(
                status_code=404,
                detail=f"test_exam_data.json not found for case {request.case_id}"
            )

        print(f"[DEBUG] File found, attempting to read JSON data")
        with open(json_path, 'r') as file:
            try:
                data = json.load(file)
                print(f"[DEBUG] Successfully loaded JSON data, size: {len(str(data))} bytes")
            except json.JSONDecodeError as e:
                print(f"[{datetime.now()}] ❌ JSON parsing error: {str(e)}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid JSON in test_exam_data.json: {str(e)}"
                )

        # Get the test category
        print(f"[DEBUG] Looking for test type: {request.test_type}")
        test_category = data.get(request.test_type)
        if not test_category:
            print(f"[{datetime.now()}] ❌ Test type not found: {request.test_type}")
            print(f"[DEBUG] Available test types: {list(data.keys())}")
            raise HTTPException(
                status_code=404,
                detail=f"Test type {request.test_type} not found"
            )

        # Get the specific test
        print(f"[DEBUG] Looking for test name: {request.test_name}")
        test_data = test_category.get(request.test_name)
        if not test_data:
            print(f"[{datetime.now()}] ❌ Test name not found: {request.test_name}")
            
            # Load case_cover.json and update error structure
            error_path = f"case-data/case{request.case_id}/case_cover.json"
            with open(error_path, 'r') as file:
                error_data = json.load(file)
            
            # Initialize or update error structure
            if "error" not in error_data:
                error_data["error"] = {
                    "type": request.test_type,
                    "name": request.test_name,
                    "comments": []
                }
            
            # Append the new comment
            error_data["error"]["comments"].append(request.comment)
            
            # Save the updated error data
            with open(error_path, 'w') as file:
                json.dump(error_data, file, indent=4)
            
            print(f"[DEBUG] Available tests in {request.test_type}: {list(test_category.keys())}")
            return {
                "message": "Comment added to error log",
                "test_name": request.test_name,
                "comments": error_data["error"]["comments"],
                "total_comments": len(error_data["error"]["comments"])
            }

        # Initialize comments array if it doesn't exist
        if "comments" not in test_data:
            print(f"[DEBUG] Initializing comments array for {request.test_name}")
            test_data["comments"] = []

        # Add the new comment
        print(f"[DEBUG] Adding new comment to {request.test_name}")
        test_data["comments"].append(request.comment)
        print(f"[DEBUG] Comment added, new comment count: {len(test_data['comments'])}")
        
        # Save the updated JSON
        print(f"[DEBUG] Saving updated JSON to {json_path}")
        try:
            with open(json_path, 'w') as file:
                json.dump(data, file, indent=4)
            print(f"[{datetime.now()}] ✅ Successfully saved updated JSON")
        except Exception as e:
            print(f"[{datetime.now()}] ❌ Error saving JSON: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to save updated JSON: {str(e)}"
            )

        return {
            "message": "Comment added successfully",
            "test_name": request.test_name,
            "comments": test_data["comments"],
            "total_comments": len(test_data["comments"])
        }
    except HTTPException:
        # Re-raise HTTP exceptions without modification
        raise
    except Exception as e:
        print(f"[{datetime.now()}] ❌ Unexpected error: {str(e)}")
        print(f"[DEBUG] Error type: {type(e).__name__}")
        print(f"[DEBUG] Full error details: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred: {str(e)}"
        )

@router.delete("/remove")
async def remove_test_comment(request: CommentDeleteRequest):
    """
    Remove a specific comment from the test data in test_exam_data.json
    
    Args:
        request: CommentDeleteRequest containing case_id, test_type, test_name, and comment_index
    """
    try:
        print(f"[{datetime.now()}] 🔍 Received comment deletion request for case {request.case_id}")
        print(f"[DEBUG] Request details: test_type={request.test_type}, test_name={request.test_name}, comment_index={request.comment_index}")
        
        json_path = f"case-data/case{request.case_id}/test_exam_data.json"
        print(f"[DEBUG] Looking for file at: {json_path}")
        
        if not os.path.exists(json_path):
            print(f"[{datetime.now()}] ❌ File not found: {json_path}")
            raise HTTPException(
                status_code=404,
                detail=f"test_exam_data.json not found for case {request.case_id}"
            )

        print(f"[DEBUG] File found, attempting to read JSON data")
        with open(json_path, 'r') as file:
            try:
                data = json.load(file)
                print(f"[DEBUG] Successfully loaded JSON data, size: {len(str(data))} bytes")
            except json.JSONDecodeError as e:
                print(f"[{datetime.now()}] ❌ JSON parsing error: {str(e)}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid JSON in test_exam_data.json: {str(e)}"
                )

        # Get the test category
        print(f"[DEBUG] Looking for test type: {request.test_type}")
        test_category = data.get(request.test_type)
        if not test_category:
            print(f"[{datetime.now()}] ❌ Test type not found: {request.test_type}")
            print(f"[DEBUG] Available test types: {list(data.keys())}")
            raise HTTPException(
                status_code=404,
                detail=f"Test type {request.test_type} not found"
            )

        # Get the specific test
        print(f"[DEBUG] Looking for test name: {request.test_name}")
        test_data = test_category.get(request.test_name)
        if not test_data:
            print(f"[{datetime.now()}] ❌ Test name not found: {request.test_name}")
            print(f"[DEBUG] Available tests in {request.test_type}: {list(test_category.keys())}")
            raise HTTPException(
                status_code=404,
                detail=f"Test {request.test_name} not found"
            )

        # Check if comments exist
        if "comments" not in test_data or not test_data["comments"]:
            print(f"[{datetime.now()}] ❌ No comments found for test: {request.test_name}")
            raise HTTPException(
                status_code=404,
                detail="No comments found for this test"
            )

        # Validate comment index
        print(f"[DEBUG] Validating comment index: {request.comment_index}")
        print(f"[DEBUG] Total comments: {len(test_data['comments'])}")
        if request.comment_index < 0 or request.comment_index >= len(test_data["comments"]):
            print(f"[{datetime.now()}] ❌ Invalid comment index: {request.comment_index}")
            raise HTTPException(
                status_code=400,
                detail=f"Invalid comment index. Must be between 0 and {len(test_data['comments']) - 1}"
            )

        # Remove the comment at the specified index
        print(f"[DEBUG] Removing comment at index {request.comment_index}")
        removed_comment = test_data["comments"].pop(request.comment_index)
        print(f"[DEBUG] Comment removed: {removed_comment[:50]}..." if len(removed_comment) > 50 else f"[DEBUG] Comment removed: {removed_comment}")
        
        # Save the updated JSON
        print(f"[DEBUG] Saving updated JSON to {json_path}")
        try:
            with open(json_path, 'w') as file:
                json.dump(data, file, indent=4)
            print(f"[{datetime.now()}] ✅ Successfully saved updated JSON")
        except Exception as e:
            print(f"[{datetime.now()}] ❌ Error saving JSON: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to save updated JSON: {str(e)}"
            )

        return {
            "message": "Comment removed successfully",
            "test_name": request.test_name,
            "removed_comment": removed_comment,
            "remaining_comments": len(test_data["comments"]),
            "comments": test_data["comments"]
        }
    except HTTPException:
        # Re-raise HTTP exceptions without modification
        raise
    except Exception as e:
        print(f"[{datetime.now()}] ❌ Unexpected error: {str(e)}")
        print(f"[DEBUG] Error type: {type(e).__name__}")
        print(f"[DEBUG] Full error details: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred: {str(e)}"
        ) 
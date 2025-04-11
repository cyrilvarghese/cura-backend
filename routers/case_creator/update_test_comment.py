from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import json
import os

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
        print(f"Received comment update for case {request.case_id}, test {request.test_name}")
        
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

        # Initialize comments array if it doesn't exist
        if "comments" not in test_data:
            test_data["comments"] = []

        # Add the new comment
        test_data["comments"].append(request.comment)
        
        # Save the updated JSON
        with open(json_path, 'w') as file:
            json.dump(data, file, indent=4)

        return {
            "message": "Comment added successfully",
            "test_name": request.test_name,
            "comments": test_data["comments"],
            "total_comments": len(test_data["comments"])
        }
    except Exception as e:
        print(f"Error: {str(e)}")
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
        print(f"Received comment deletion for case {request.case_id}, test {request.test_name}")
        
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

        # Check if comments exist
        if "comments" not in test_data or not test_data["comments"]:
            raise HTTPException(
                status_code=404,
                detail="No comments found for this test"
            )

        # Validate comment index
        if request.comment_index < 0 or request.comment_index >= len(test_data["comments"]):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid comment index. Must be between 0 and {len(test_data['comments']) - 1}"
            )

        # Remove the comment at the specified index
        removed_comment = test_data["comments"].pop(request.comment_index)
        
        # Save the updated JSON
        with open(json_path, 'w') as file:
            json.dump(data, file, indent=4)

        return {
            "message": "Comment removed successfully",
            "test_name": request.test_name,
            "removed_comment": removed_comment,
            "remaining_comments": len(test_data["comments"]),
            "comments": test_data["comments"]
        }
    except Exception as e:
        print(f"Error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred: {str(e)}"
        ) 
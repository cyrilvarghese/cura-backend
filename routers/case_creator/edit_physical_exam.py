"""
API router for editing and managing physical exam data types.

This module provides endpoints to:
- Convert mixed type physical_exam findings to text type (PUT /edit-physical-exam/mixed-to-text)
- Convert text type physical_exam findings to mixed type (PUT /edit-physical-exam/text-to-mixed)
- Add new text type physical exam (POST /edit-physical-exam/add-text)
- Add new mixed type physical exam with image URLs (POST /edit-physical-exam/add-mixed)
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import json
import os

router = APIRouter(
    tags=["physical-exam"]
)

class AddTextPhysicalExamRequest(BaseModel):
    case_id: str
    test_name: str
    purpose: str
    text_content: str
    interpretation: Optional[str] = ""
    status: Optional[str] = "completed"

class AddMixedPhysicalExamRequest(BaseModel):
    case_id: str
    test_name: str
    purpose: str
    text_content: str
    url: List[str]  # Array of image URLs
    interpretation: Optional[str] = ""
    status: Optional[str] = "completed"

class RemovePhysicalExamRequest(BaseModel):
    case_id: str
    test_name: str

class EditPhysicalExamRequest(BaseModel):
    case_id: str
    test_name: str
    purpose: Optional[str] = None
    text_content: Optional[str] = None
    url: Optional[List[str]] = None  # For mixed type - image URLs
    interpretation: Optional[str] = None
    status: Optional[str] = None

class AddTestResponse(BaseModel):
    message: str
    case_id: str
    test_name: str
    test_type: str
    content_type: str
    success: bool

class AddMixedTestResponse(BaseModel):
    message: str
    case_id: str
    test_name: str
    test_type: str
    content_type: str
    text_content: str
    image_urls: List[str]
    success: bool

class RemoveTestResponse(BaseModel):
    message: str
    case_id: str
    test_name: str
    test_type: str
    success: bool

class EditTestResponse(BaseModel):
    message: str
    case_id: str
    test_name: str
    test_type: str
    updated_fields: List[str]
    current_type: str
    success: bool

@router.post("/add-text")
async def add_text_physical_exam(request: AddTextPhysicalExamRequest):
    """
    Add a new text type physical exam finding to the case data.
    
    Args:
        request: AddTextPhysicalExamRequest containing case details and text content
    
    Returns:
        AddTestResponse with creation details
    """
    try:
        print(f"Adding new text physical exam for case {request.case_id}, test {request.test_name}")
        
        json_path = f"case-data/case{request.case_id}/test_exam_data.json"
        
        if not os.path.exists(json_path):
            raise HTTPException(
                status_code=404,
                detail=f"test_exam_data.json not found for case {request.case_id}"
            )

        with open(json_path, 'r') as file:
            data = json.load(file)

        # Get or create the physical_exam category
        if "physical_exam" not in data:
            data["physical_exam"] = {}
        
        physical_exam = data["physical_exam"]
        
        # Log for debugging duplicate check
        print(f"DEBUG: Checking for duplicate test name")
        print(f"DEBUG: Requested test name: '{request.test_name}'")
        print(f"DEBUG: Existing physical exam tests: {list(physical_exam.keys())}")
        
        # Check if test already exists
        test_exists = request.test_name in physical_exam
        if test_exists:
            print(f"DEBUG: Test {request.test_name} already exists, updating instead of creating new")
        else:
            print(f"DEBUG: Creating new test {request.test_name}")
        
        # Create or update text type physical exam
        physical_exam[request.test_name] = {
            "purpose": request.purpose,
            "findings": {
                "type": "text",
                "content": request.text_content
            },
            "status": request.status,
            "interpretation": request.interpretation
        }
        
        # Save the updated JSON
        with open(json_path, 'w') as file:
            json.dump(data, file, indent=4)

        return AddTestResponse(
            message=f"Successfully {'updated' if test_exists else 'added new'} text type physical exam: {request.test_name}",
            case_id=request.case_id,
            test_name=request.test_name,
            test_type="physical_exam",
            content_type="text",
            success=True
        )
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error adding text physical exam: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while adding the test: {str(e)}"
        )

@router.post("/add-mixed")
async def add_mixed_physical_exam(request: AddMixedPhysicalExamRequest):
    """
    Add a new mixed type physical exam finding with image URLs to the case data.
    
    Args:
        request: AddMixedPhysicalExamRequest containing case details, text content, and image URLs
    
    Returns:
        AddMixedTestResponse with creation details including image URLs
    """
    try:
        print(f"Adding new mixed physical exam for case {request.case_id}, test {request.test_name} with {len(request.url)} image URLs")
        
        json_path = f"case-data/case{request.case_id}/test_exam_data.json"
        
        if not os.path.exists(json_path):
            raise HTTPException(
                status_code=404,
                detail=f"test_exam_data.json not found for case {request.case_id}"
            )

        with open(json_path, 'r') as file:
            data = json.load(file)

        # Get or create the physical_exam category
        if "physical_exam" not in data:
            data["physical_exam"] = {}
        
        physical_exam = data["physical_exam"]
        
        # Check if test already exists
        test_exists = request.test_name in physical_exam
        existing_image_urls = []
        
        if test_exists:
            print(f"DEBUG: Test {request.test_name} already exists, updating instead of creating new")
            
            # Check if existing test has image type findings and extract URLs
            existing_test = physical_exam[request.test_name]
            if "findings" in existing_test:
                existing_findings = existing_test["findings"]
                if existing_findings.get("type") == "image":
                    # Extract existing image URLs
                    existing_content = existing_findings.get("content", {})
                    existing_urls = existing_content.get("url", [])
                    if isinstance(existing_urls, str):
                        existing_urls = [existing_urls]
                    elif not isinstance(existing_urls, list):
                        existing_urls = []
                    existing_image_urls = existing_urls
                    print(f"DEBUG: Found existing image URLs: {existing_image_urls}")
        else:
            print(f"DEBUG: Creating new test {request.test_name}")
        
        # Validate that URLs are provided
        if not request.url or len(request.url) == 0:
            raise HTTPException(
                status_code=400,
                detail="At least one image URL must be provided"
            )
        
        # Combine existing image URLs with new ones, removing duplicates
        all_image_urls = existing_image_urls.copy()
        for url in request.url:
            if url not in all_image_urls:
                all_image_urls.append(url)
        
        print(f"DEBUG: Final image URLs for mixed type: {all_image_urls}")
        
        # Create or update mixed type physical exam (completely overwrite existing)
        physical_exam[request.test_name] = {
            "purpose": request.purpose,
            "findings": {
                "type": "mixed",
                "content": [
                    {
                        "type": "text",
                        "content": request.text_content
                    },
                    {
                        "type": "image",
                        "content": {
                            "url": all_image_urls,
                            "altText": f"Images for {request.test_name}",
                            "caption": f"Physical exam images for {request.test_name}"
                        }
                    }
                ]
            },
            "status": request.status,
            "interpretation": request.interpretation
        }
        
        # Save the updated JSON
        with open(json_path, 'w') as file:
            json.dump(data, file, indent=4)

        return AddMixedTestResponse(
            message=f"Successfully {'updated' if test_exists else 'added new'} mixed type physical exam: {request.test_name} with {len(request.url)} image URLs",
            case_id=request.case_id,
            test_name=request.test_name,
            test_type="physical_exam",
            content_type="mixed",
            text_content=request.text_content,
            image_urls=request.url,
            success=True
        )
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error adding mixed physical exam: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while adding the test: {str(e)}"
        )

@router.put("/edit-exam")
async def edit_physical_exam(request: EditPhysicalExamRequest):
    """
    Edit an existing physical exam by completely replacing it with new data.
    
    Args:
        request: EditPhysicalExamRequest containing case_id, test_name and fields to update
    
    Returns:
        EditTestResponse with edit details
    """
    try:
        print(f"Editing physical exam {request.test_name} for case {request.case_id}")
        
        json_path = f"case-data/case{request.case_id}/test_exam_data.json"
        
        if not os.path.exists(json_path):
            raise HTTPException(
                status_code=404,
                detail=f"test_exam_data.json not found for case {request.case_id}"
            )

        with open(json_path, 'r') as file:
            data = json.load(file)

        # Get the physical_exam category
        physical_exam = data.get("physical_exam")
        if not physical_exam:
            raise HTTPException(
                status_code=404,
                detail="physical_exam category not found"
            )

        # Check if the test exists
        if request.test_name not in physical_exam:
            raise HTTPException(
                status_code=404,
                detail=f"Physical exam test {request.test_name} not found"
            )
        
        # Determine what type to create based on whether URLs are provided
        if request.url and len(request.url) > 0:
            # Create mixed type test
            test_type = "mixed"
            physical_exam[request.test_name] = {
                "purpose": request.purpose or "",
                "findings": {
                    "type": "mixed",
                    "content": [
                        {
                            "type": "text",
                            "content": request.text_content or ""
                        },
                        {
                            "type": "image",
                            "content": {
                                "url": request.url,
                                "altText": f"Images for {request.test_name}",
                                "caption": f"Physical exam images for {request.test_name}"
                            }
                        }
                    ]
                },
                "status": request.status or "completed",
                "interpretation": request.interpretation or ""
            }
        else:
            # Create text type test
            test_type = "text"
            physical_exam[request.test_name] = {
                "purpose": request.purpose or "",
                "findings": {
                    "type": "text",
                    "content": request.text_content or ""
                },
                "status": request.status or "completed",
                "interpretation": request.interpretation or ""
            }
        
        print(f"DEBUG: Replaced test with type: {test_type}")
        
        # Save the updated JSON
        with open(json_path, 'w') as file:
            json.dump(data, file, indent=4)

        # Determine which fields were provided (non-None)
        updated_fields = []
        if request.purpose is not None:
            updated_fields.append("purpose")
        if request.text_content is not None:
            updated_fields.append("text_content")
        if request.url is not None:
            updated_fields.append("url")
        if request.interpretation is not None:
            updated_fields.append("interpretation")
        if request.status is not None:
            updated_fields.append("status")

        return EditTestResponse(
            message=f"Successfully replaced physical exam: {request.test_name} with {test_type} type",
            case_id=request.case_id,
            test_name=request.test_name,
            test_type="physical_exam",
            updated_fields=updated_fields,
            current_type=test_type,
            success=True
        )
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error editing physical exam: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while editing the test: {str(e)}"
        )

@router.delete("/remove-exam")
async def remove_physical_exam(request: RemovePhysicalExamRequest):
    """
    Remove a physical exam test from the case data.
    
    Args:
        request: RemovePhysicalExamRequest containing case_id and test_name
    
    Returns:
        RemoveTestResponse with removal details
    """
    try:
        print(f"Removing physical exam test {request.test_name} from case {request.case_id}")
        
        json_path = f"case-data/case{request.case_id}/test_exam_data.json"
        
        if not os.path.exists(json_path):
            raise HTTPException(
                status_code=404,
                detail=f"test_exam_data.json not found for case {request.case_id}"
            )

        with open(json_path, 'r') as file:
            data = json.load(file)

        # Get the physical_exam category
        physical_exam = data.get("physical_exam")
        if not physical_exam:
            raise HTTPException(
                status_code=404,
                detail="physical_exam category not found"
            )

        # Check if the test exists
        if request.test_name not in physical_exam:
            raise HTTPException(
                status_code=404,
                detail=f"Physical exam test {request.test_name} not found"
            )
        
        # Remove the test
        del physical_exam[request.test_name]
        
        # Save the updated JSON
        with open(json_path, 'w') as file:
            json.dump(data, file, indent=4)

        return RemoveTestResponse(
            message=f"Successfully removed physical exam test: {request.test_name}",
            case_id=request.case_id,
            test_name=request.test_name,
            test_type="physical_exam",
            success=True
        )
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error removing physical exam test: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while removing the test: {str(e)}"
        ) 
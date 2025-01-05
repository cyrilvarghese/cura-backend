from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
import os
from datetime import datetime
from typing import Optional
import shutil
from pydantic import BaseModel
import json
from enum import Enum
from .helpers.image_downloader import download_image
from .helpers.image_extractor import extract_and_save

router = APIRouter(
    prefix="/test-image",
    tags=["create-data"]
)

class TestType(str, Enum):
    """Enum for test types"""
    PHYSICAL_EXAM = "physical_exam"
    LAB_TEST = "lab_test"

class UploadResponse(BaseModel):
    """Response model for successful upload"""
    case_id: str
    test_name: str
    test_type: TestType
    file_path: str
    message: str

class UploadFromUrlRequest(BaseModel):
    """Request model for URL-based image upload"""
    case_id: str
    test_name: str
    test_type: TestType
    image_url: str

def ensure_assets_directory(case_id: str) -> str:
    """
    Ensure the assets directory exists for the given case ID
    Returns the full path to the assets directory
    """
    assets_path = f"case-data/case{case_id}/assets"
    os.makedirs(assets_path, exist_ok=True)
    return assets_path

def validate_image_file(file: UploadFile) -> bool:
    """
    Validate if the uploaded file is an image
    """
    allowed_extensions = {'.jpg', '.jpeg', '.png'}
    file_ext = os.path.splitext(file.filename)[1].lower()
    return file_ext in allowed_extensions

def update_test_exam_data(case_id: str, test_name: str, test_type: TestType, image_url: str) -> bool:
    """
    Update the img_url property in test_exam_data.json for the specified test
    
    Args:
        case_id: The ID of the case
        test_name: Name of the test/examination
        test_type: Type of test (physical_exam or lab_test)
        image_url: URL of the uploaded image
    
    Returns:
        bool: True if update successful, False if test not found
    """
    json_path = f"case-data/case{case_id}/test_exam_data.json"
    
    try:
        with open(json_path, 'r') as file:
            data = json.load(file)
        
        # Get the correct category (physical_exam or lab_test)
        test_category = data.get(test_type.value, {})
        if not test_category:
            return False
            
        # Find the test by name
        test_data = test_category.get(test_name)
        if not test_data:
            return False
            
        # Update the image URL in the correct field based on test type
        if test_type == TestType.PHYSICAL_EXAM:
            # Update findings if it exists
            if "findings" in test_data:
                if test_data["findings"].get("type") == "mixed":
                    # If findings is already mixed type, append to content
                    image_content = {
                        "type": "image",
                        "content": {
                            "url": image_url,
                            "altText": f"Image for {test_name}",
                            "caption": f"Physical examination image for {test_name}"
                        }
                    }
                    # Check if content is a list and contains no existing image
                    if isinstance(test_data["findings"]["content"], list):
                        # Remove any existing image entries
                        test_data["findings"]["content"] = [
                            item for item in test_data["findings"]["content"] 
                            if item.get("type") != "image"
                        ]
                        test_data["findings"]["content"].append(image_content)
                    else:
                        test_data["findings"]["content"] = [
                            {"type": "text", "content": test_data["findings"]["content"]},
                            image_content
                        ]
                elif test_data["findings"].get("type") == "image":
                    # If type is image, just update the URL
                    test_data["findings"]["content"]["url"] = image_url
                # If not mixed or image type, do nothing
        else:  # LAB_TEST
            # Update results if it exists
            if "results" in test_data:
                if test_data["results"].get("type") == "mixed":
                    # If results is already mixed type, append to content
                    image_content = {
                        "type": "image",
                        "content": {
                            "url": image_url,
                            "altText": f"Image for {test_name}",
                            "caption": f"Laboratory test image for {test_name}"
                        }
                    }
                    # Check if content is a list and contains no existing image
                    if isinstance(test_data["results"]["content"], list):
                        # Remove any existing image entries
                        test_data["results"]["content"] = [
                            item for item in test_data["results"]["content"] 
                            if item.get("type") != "image"
                        ]
                        test_data["results"]["content"].append(image_content)
                    else:
                        test_data["results"]["content"] = [
                            {"type": "text", "content": test_data["results"]["content"]},
                            image_content
                        ]
                elif test_data["results"].get("type") == "image":
                    # If type is image, just update the URL
                    test_data["results"]["content"]["url"] = image_url
                # If not mixed or image type, do nothing
        
        # Save the updated JSON
        with open(json_path, 'w') as file:
            json.dump(data, file, indent=4)
        return True
            
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"test_exam_data.json not found for case {case_id}"
        )
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=500,
            detail=f"Invalid JSON format in test_exam_data.json for case {case_id}"
        )

@router.post("/upload", response_model=UploadResponse)
async def upload_test_image(
    case_id: str = Form(...),
    test_name: str = Form(...),
    test_type: TestType = Form(...),
    file: UploadFile = File(...),
):
    """
    Upload a test image for a specific case and test name using form data
    
    Args:
        case_id: The ID of the case (from form)
        test_name: Name of the test/examination (from form)
        test_type: Type of test (physical_exam or lab_test) (from form)
        file: The image file to upload
    
    Returns:
        JSON response with upload details
    """
    try:
        # Add detailed error logging at the start
        print(f"""
                [DEBUG] Upload attempt details:
                - Case ID: {case_id}
                - Test Name: {test_name}
                - Test Type: {test_type}
                - File Name: {file.filename}
                - File Content Type: {file.content_type}
                """)

        # Validate image file
        if not validate_image_file(file):
            print(f"[ERROR] Invalid file type: {file.filename} ({file.content_type})")
            raise HTTPException(
                status_code=400,
                detail="Invalid file type. Only JPG and PNG files are allowed."
            )

        # Ensure assets directory exists
        assets_dir = ensure_assets_directory(case_id)

        # Create file path with original extension
        file_ext = os.path.splitext(file.filename)[1].lower()
        sanitized_test_name = test_name.replace(" ", "_").lower()
        file_name = f"{test_type.value}_{sanitized_test_name}{file_ext}"
        file_path = os.path.join(assets_dir, file_name)

        # Save the uploaded file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Generate response
        relative_path = f"/case-images/case{case_id}/assets/{file_name}"
        
        # Update test_exam_data.json
        if not update_test_exam_data(case_id, test_name, test_type, relative_path):
            print(f"Warning: Test '{test_name}' not found in {test_type.value} category in test_exam_data.json")
        
        return UploadResponse(
            case_id=case_id,
            test_name=test_name,
            test_type=test_type,
            file_path=relative_path,
            message="Test image uploaded successfully"
        )

    except Exception as e:
        error_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        error_message = f"""
                            [{error_timestamp}] ❌ Error in upload_test_image:
                            - Error Type: {type(e).__name__}
                            - Error Message: {str(e)}
                            - Case ID: {case_id}
                            - Test Name: {test_name}
                            - Test Type: {test_type}
                            - File Details: {file.filename if file else 'No file'}
                            """
        print(error_message)
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/delete/{case_id}/{test_type}/{test_name}")
async def delete_test_image(
    case_id: str, 
    test_type: TestType,
    test_name: str
):
    """
    Delete a test image for a specific case and test name
    
    Args:
        case_id: The ID of the case
        test_type: Type of test (physical_exam or lab_test)
        test_name: Name of the test/examination
    
    Returns:
        JSON response confirming deletion
    """
    try:
        assets_dir = f"case-data/case{case_id}/assets"
        sanitized_test_name = test_name.replace(" ", "_").lower()
        base_filename = f"{test_type.value}_{sanitized_test_name}"
        
        # Check for both possible extensions
        for ext in ['.jpg', '.jpeg', '.png']:
            file_path = os.path.join(assets_dir, f"{base_filename}{ext}")
            if os.path.exists(file_path):
                os.remove(file_path)
                return JSONResponse(
                    content={
                        "message": f"Test image {test_name} deleted successfully",
                        "case_id": case_id,
                        "test_type": test_type,
                        "test_name": test_name
                    }
                )
        
        raise HTTPException(
            status_code=404,
            detail=f"Test image {test_name} not found for case {case_id}"
        )

    except Exception as e:
        error_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        error_message = f"[{error_timestamp}] ❌ Error in delete_test_image: {str(e)}"
        print(error_message)
        raise HTTPException(status_code=500, detail=str(e)) 

@router.post("/upload-from-url", response_model=UploadResponse)
async def upload_test_image_from_url(request: UploadFromUrlRequest):
    """
    Upload a test image from a URL for a specific case and test name
    """
    try:
        print(f"""
                [DEBUG] URL Upload attempt details:
                - Case ID: {request.case_id}
                - Test Name: {request.test_name}
                - Test Type: {request.test_type}
                - Image URL: {request.image_url}
                """)

        # Ensure assets directory exists
        assets_dir = ensure_assets_directory(request.case_id)

        # Create file path
        sanitized_test_name = request.test_name.replace(" ", "_").lower()
        file_name = f"{request.test_type.value}_{sanitized_test_name}.jpg"
        file_path = os.path.join(assets_dir, file_name)

        # Download the image
        saved_path, response_code = await download_image(request.image_url, file_path)

        # Generate response
        relative_path = saved_path if response_code == 403 else f"/case-images/case{request.case_id}/assets/{file_name}"
        
        # Update test_exam_data.json
        if not update_test_exam_data(request.case_id, request.test_name, request.test_type, relative_path):
            print(f"Warning: Test '{request.test_name}' not found in {request.test_type.value} category in test_exam_data.json")
        
        return UploadResponse(
            case_id=request.case_id,
            test_name=request.test_name,
            test_type=request.test_type,
            file_path=relative_path,
            message="Test image uploaded successfully from URL"
        )

    except Exception as e:
        error_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        error_message = f"""
                            [{error_timestamp}] ❌ Error in upload_test_image_from_url:
                            - Error Type: {type(e).__name__}
                            - Error Message: {str(e)}
                            - Case ID: {request.case_id}
                            - Test Name: {request.test_name}
                            - Test Type: {request.test_type}
                            - Image URL: {request.image_url}
                            """
        print(error_message)
        raise HTTPException(status_code=500, detail=str(e)) 
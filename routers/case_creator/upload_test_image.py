from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
import os
from datetime import datetime
from typing import Optional, List
import shutil
from pydantic import BaseModel
import json
from enum import Enum
from .helpers.image_downloader import download_image
from .helpers.image_extractor import extract_and_save
import time
import traceback

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

class TestImageUploadResponse(BaseModel):
    message: str
    image_urls: List[str]
    case_id: str
    test_name: str
    test_type: str
    file_path: str  # This will contain the directory path

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
    allowed_extensions = {'.jpg', '.jpeg', '.png','.webp','.avif'}
    file_ext = os.path.splitext(file.filename)[1].lower()
    return file_ext in allowed_extensions

def update_test_exam_data(case_id: str, test_name: str, test_type: TestType, image_urls: List[str]) -> bool:
    """
    Update the test_exam_data.json file to add image URLs to the appropriate structure
    
    Args:
        case_id: The case ID
        test_name: The name of the test
        test_type: The type of test (physical_exam or lab_test)
        image_urls: List of image URLs to store
    
    Returns:
        True if successful, False otherwise
    """
    try:
        json_path = f"case-data/case{case_id}/test_exam_data.json"
        
        # Create the file if it doesn't exist
        if not os.path.exists(json_path):
            with open(json_path, 'w') as f:
                json.dump({
                    "physical_exam": {},
                    "lab_test": {}
                }, f, indent=4)
        
        # Read the existing data
        with open(json_path, 'r') as f:
            data = json.load(f)
        
        # Get the test category
        test_category = data.get(test_type.value, {})
        
        # Get or create the test entry
        test_entry = test_category.get(test_name, {})
        
        # Make sure we have a results or findings key based on test type
        results_key = "findings" if test_type.value == "physical_exam" else "results"
        if results_key not in test_entry:
            test_entry[results_key] = {}
        
        # Get the results/findings object
        results = test_entry[results_key]
        
        # Check the type of results
        if "type" not in results:
            # If no type is specified, set it to "image"
            results["type"] = "image"
            results["content"] = {
                "url": image_urls,
                "altText": f"Images for {test_name}",
                "caption": f"Test images for {test_name}"
            }
        elif results["type"] == "image":
            # If type is already "image", append to existing URLs
            existing_urls = results["content"].get("url", [])
            if not isinstance(existing_urls, list):
                existing_urls = [existing_urls]
            
            # Filter out example.com URLs
            existing_urls = [url for url in existing_urls if not "example.com" in url]
            
            # Combine existing and new URLs, removing duplicates
            combined_urls = existing_urls + [url for url in image_urls if url not in existing_urls]
            results["content"]["url"] = combined_urls
        elif results["type"] == "mixed":
            # For mixed type, find or add an image content item
            if "content" not in results:
                results["content"] = []
            
            # If content is not a list, convert it
            if not isinstance(results["content"], list):
                results["content"] = [results["content"]]
            
            # Look for an existing image item
            image_item_found = False
            for i, item in enumerate(results["content"]):
                if isinstance(item, dict) and item.get("type") == "image":
                    image_item_found = True
                    # Get existing URLs
                    existing_urls = item["content"].get("url", [])
                    if not isinstance(existing_urls, list):
                        existing_urls = [existing_urls]
                    
                    # Filter out example.com URLs
                    existing_urls = [url for url in existing_urls if not "example.com" in url]
                    
                    # Combine existing and new URLs, removing duplicates
                    combined_urls = existing_urls + [url for url in image_urls if url not in existing_urls]
                    item["content"]["url"] = combined_urls
                    
                    # Update the item in the content list
                    results["content"][i] = item
                    break
            
            # If no image item was found, add a new one
            if not image_item_found:
                results["content"].append({
                    "type": "image",
                    "content": {
                        "url": image_urls,
                        "altText": f"Images for {test_name}",
                        "caption": f"Test images for {test_name}"
                    }
                })
        else:
            # For other types (text, table), convert to mixed type
            old_content = results.get("content", "")
            old_type = results.get("type", "text")
            
            # Create a mixed type with the old content and new image
            results["type"] = "mixed"
            results["content"] = [
                {
                    "type": old_type,
                    "content": old_content
                },
                {
                    "type": "image",
                    "content": {
                        "url": image_urls,
                        "altText": f"Images for {test_name}",
                        "caption": f"Test images for {test_name}"
                    }
                }
            ]
        
        # Update the test entry in the test category
        test_category[test_name] = test_entry
        
        # Update the test category in the data
        data[test_type.value] = test_category
        
        # Write the updated data back to the file
        with open(json_path, 'w') as f:
            json.dump(data, f, indent=4)
        
        print(f"Successfully updated test_exam_data.json with URLs: {image_urls}")
        return True
    except Exception as e:
        print(f"Error updating test_exam_data.json: {str(e)}")
        traceback.print_exc()  # Print the full traceback for debugging
        return False

@router.post("/upload", response_model=TestImageUploadResponse)
async def upload_test_image(
    case_id: str = Form(...),
    test_name: str = Form(...),
    test_type: TestType = Form(...),
    files: List[UploadFile] = File(...),
):
    """
    Upload one or more images for a test and update the test_exam_data.json file
    
    Args:
        case_id: The case ID
        test_name: The name of the test
        test_type: The type of test (physical_exam or lab_test)
        files: One or more image files to upload
    
    Returns:
        A dictionary with the uploaded image URLs and metadata
    """
    try:
        # Create directory if it doesn't exist
        case_dir = f"case-data/case{case_id}"
        os.makedirs(case_dir, exist_ok=True)
        
        # Use assets directory instead of images
        assets_dir = ensure_assets_directory(case_id)
        
        new_image_urls = []
        
        for file in files:
            # Generate a unique filename
            timestamp = int(time.time() * 1000)
            filename = f"{test_name.replace(' ', '_')}_{timestamp}_{file.filename}"
            
            # Save the file to assets directory
            file_path = f"{assets_dir}/{filename}"
            
            with open(file_path, "wb") as f:
                content = await file.read()
                f.write(content)
            
            # Create the relative URL for the image (using assets path)
            image_url = f"/case-images/case{case_id}/assets/{filename}"
            new_image_urls.append(image_url)
        
        # Update the test_exam_data.json file with all image URLs
        update_test_exam_data(case_id, test_name, test_type, new_image_urls)
        
        # Get all image URLs for this test (including previously existing ones)
        all_image_urls = get_all_image_urls(case_id, test_name, test_type)
        
        return {
            "message": f"Successfully uploaded {len(new_image_urls)} image(s) for {test_name}",
            "image_urls": all_image_urls,  # Return all URLs, not just the new ones
            "case_id": case_id,
            "test_name": test_name,
            "test_type": test_type.value,
            "file_path": assets_dir
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while uploading the image: {str(e)}"
        )

def get_all_image_urls(case_id: str, test_name: str, test_type: TestType) -> List[str]:
    """
    Get all image URLs for a specific test
    
    Args:
        case_id: The case ID
        test_name: The name of the test
        test_type: The type of test
        
    Returns:
        List of all image URLs for the test
    """
    try:
        json_path = f"case-data/case{case_id}/test_exam_data.json"
        
        if not os.path.exists(json_path):
            return []
        
        with open(json_path, 'r') as f:
            data = json.load(f)
        
        test_category = data.get(test_type.value, {})
        test_entry = test_category.get(test_name, {})
        
        results_key = "findings" if test_type.value == "physical_exam" else "results"
        if results_key not in test_entry:
            return []
        
        results = test_entry[results_key]
        
        if results["type"] == "image":
            urls = results["content"].get("url", [])
            if not isinstance(urls, list):
                urls = [urls]
            # Filter out example.com URLs
            return [url for url in urls if not "example.com" in url]
        elif results["type"] == "mixed":
            all_urls = []
            for item in results["content"]:
                if isinstance(item, dict) and item.get("type") == "image":
                    urls = item["content"].get("url", [])
                    if not isinstance(urls, list):
                        urls = [urls]
                    # Filter out example.com URLs
                    all_urls.extend([url for url in urls if not "example.com" in url])
            return all_urls
        
        return []
    except Exception as e:
        print(f"Error getting all image URLs: {str(e)}")
        return []

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
        # Path to the test_exam_data.json file
        json_path = f"case-data/case{case_id}/test_exam_data.json"
        
        # Check if the file exists
        if not os.path.exists(json_path):
            raise HTTPException(
                status_code=404,
                detail=f"Test data file not found for case {case_id}"
            )
        
        # Read the existing data
        with open(json_path, 'r') as f:
            data = json.load(f)
        
        # Get the test category
        test_category = data.get(test_type.value, {})
        
        # Check if the test exists
        if test_name not in test_category:
            raise HTTPException(
                status_code=404,
                detail=f"Test {test_name} not found in {test_type.value} category"
            )
        
        # Get the test entry
        test_entry = test_category[test_name]
        
        # Determine the key based on test type
        results_key = "findings" if test_type.value == "physical_exam" else "results"
        
        if results_key not in test_entry:
            raise HTTPException(
                status_code=404,
                detail=f"No {results_key} found for test {test_name}"
            )
        
        # Get the results/findings object
        results = test_entry[results_key]
        
        # Create a dummy URL
        dummy_url = f"https://example.com/{test_name.replace(' ', '_')}.jpg"
        
        # Update the URL based on the structure
        if results["type"] == "image":
            results["content"]["url"] = [dummy_url]
        elif results["type"] == "mixed":
            for item in results["content"]:
                if isinstance(item, dict) and item.get("type") == "image":
                    item["content"]["url"] = [dummy_url]
        
        # Write the updated data back to the file
        with open(json_path, 'w') as f:
            json.dump(data, f, indent=4)
        
        return JSONResponse(
            content={
                "message": f"Test image URLs for {test_name} replaced with dummy URL",
                "case_id": case_id,
                "test_type": test_type.value,
                "test_name": test_name,
                "dummy_url": dummy_url
            }
        )

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        error_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        error_message = f"[{error_timestamp}] ❌ Error in delete_test_image: {str(e)}"
        print(error_message)
        traceback.print_exc()  # Print the full traceback for debugging
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
        if not update_test_exam_data(request.case_id, request.test_name, request.test_type, [relative_path]):
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
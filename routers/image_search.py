from typing import List, Dict
from fastapi import APIRouter, HTTPException, Query, Depends
from langchain_community.retrievers import TavilySearchAPIRetriever
from pydantic import BaseModel
import os
from dotenv import load_dotenv
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from datetime import datetime
import json
from auth.auth_api import get_user_from_token

# Load environment variables
load_dotenv()

# Define the security scheme
security = HTTPBearer()

# Initialize router
router = APIRouter(
    prefix="/image-search",
    tags=["image-search"]
)

# Initialize Tavily retriever with custom parameters
retriever = TavilySearchAPIRetriever(
    api_key=os.getenv("TAVILY_API_KEY"),
    k=10,  # Number of results to return
    search_depth="advanced",
    include_images=True,
    include_raw_content=True,
    include_domains=["nih.gov", "pubmed.gov", "medlineplus.gov", "mayoclinic.org"]  # Medical domains
)

# Define response model
class ImageSearchResponse(BaseModel):
    images: List[Dict[str, str]]

@router.get("/search_medical_images/", response_model=ImageSearchResponse)
async def search_medical_images(
    query: str = Query(..., description="Medical image search query", example="Histopathological examination shows IgA deposits"),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Search for medical images based on a query using Tavily.
    
    Args:
        query (str): The medical image search query
        
    Returns:
        ImageSearchResponse: List of images with their URLs, titles, and sources
    """
    print(f"[IMAGE_SEARCH] 🔍 Searching images with query: {query}")
    
    # Extract token and authenticate the user
    try:
        token = credentials.credentials
        print(f"[DEBUG] Extracted JWT: {token}")
        
        print(f"[IMAGE_SEARCH] 🔐 Authenticating user...")
        user_response = await get_user_from_token(token)
        if not user_response["success"]:
            error_message = user_response.get("error", "Authentication required")
            print(f"[IMAGE_SEARCH] ❌ Authentication failed: {error_message}")
            raise HTTPException(status_code=401, detail=error_message)
        
        user_id = user_response["user"]["id"]
        print(f"[IMAGE_SEARCH] ✅ User authenticated successfully. User ID: {user_id}")
        
        try:
            # Search using Tavily
            results = retriever.get_relevant_documents(f"{query} medical images")
            
            # Process and format results
            seen_urls = set()  # Track seen URLs
            unique_images = []
            
            for doc in results:
                metadata = doc.metadata
                if "images" in metadata and metadata["images"]:
                    for image in metadata["images"]:
                        # Only add image if URL hasn't been seen before
                        if image not in seen_urls:
                            seen_urls.add(image)
                            unique_images.append({
                                "url": image,
                                "title": metadata.get("title", ""),
                                "source": metadata.get("source", "")
                            })
            
            # Ensure we only return up to 50 unique images
            return ImageSearchResponse(images=unique_images[:50])
            
        except Exception as e:
            print(f"[IMAGE_SEARCH] ❌ Error searching images: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error searching images: {str(e)}")
            
    except HTTPException as auth_error:
        print(f"[IMAGE_SEARCH] ❌ HTTP exception during authentication: {str(auth_error)}")
        raise auth_error
    except Exception as auth_error:
        print(f"[IMAGE_SEARCH] ❌ Unexpected error during authentication: {str(auth_error)}")
        raise HTTPException(status_code=401, detail="Authentication failed")

@router.get("/search")
async def search_images(
    query: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Search for images based on a query.
    """
    print(f"[IMAGE_SEARCH] 🔍 Searching images with query: {query}")
    
    # Extract token and authenticate the user
    try:
        token = credentials.credentials
        print(f"[DEBUG] Extracted JWT: {token}")
        
        print(f"[IMAGE_SEARCH] 🔐 Authenticating user...")
        user_response = await get_user_from_token(token)
        if not user_response["success"]:
            error_message = user_response.get("error", "Authentication required")
            print(f"[IMAGE_SEARCH] ❌ Authentication failed: {error_message}")
            raise HTTPException(status_code=401, detail=error_message)
        
        user_id = user_response["user"]["id"]
        print(f"[IMAGE_SEARCH] ✅ User authenticated successfully. User ID: {user_id}")
        
        try:
            # Your existing image search logic here
            # ... existing code ...
            return {"message": "Images found successfully"}
        except Exception as e:
            print(f"[IMAGE_SEARCH] ❌ Error searching images: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error searching images: {str(e)}")
            
    except HTTPException as auth_error:
        print(f"[IMAGE_SEARCH] ❌ HTTP exception during authentication: {str(auth_error)}")
        raise auth_error
    except Exception as auth_error:
        print(f"[IMAGE_SEARCH] ❌ Unexpected error during authentication: {str(auth_error)}")
        raise HTTPException(status_code=401, detail="Authentication failed") 
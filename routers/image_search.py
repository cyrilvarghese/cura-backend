from typing import List, Dict, Optional
from fastapi import APIRouter, HTTPException, Query, Depends
from tavily import TavilyClient
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

# Initialize Tavily client
tavily_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

# Define response models
class ImageResult(BaseModel):
    url: str
    description: Optional[str] = None

class SearchResult(BaseModel):
    title: str
    url: str
    content: str
    score: float

class ImageSearchResponse(BaseModel):
    query: str
    images: List[ImageResult]
    results: List[SearchResult]
    response_time: float
    total_images: int
    total_results: int

class ImageSearchRequest(BaseModel):
    query: str
    max_results: Optional[int] = 5
    search_depth: Optional[str] = "advanced"
    include_image_descriptions: Optional[bool] = True
    include_domains: Optional[List[str]] = None
    exclude_domains: Optional[List[str]] = None
    topic: Optional[str] = "general"

@router.post("/search", response_model=ImageSearchResponse)
async def search_images_with_descriptions(
    request: ImageSearchRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Advanced image search with descriptions using Tavily API.
    
    Args:
        request (ImageSearchRequest): Search parameters including query, filters, and options
        
    Returns:
        ImageSearchResponse: Comprehensive search results with images, descriptions, and related content
    """
    print(f"[IMAGE_SEARCH] 🔍 Advanced search with query: {request.query}")
    
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
            # Prepare search parameters
            search_params = {
                "query": request.query,
                "max_results": request.max_results,
                "search_depth": request.search_depth,
                "include_images": True,
                "include_image_descriptions": request.include_image_descriptions,
                "topic": request.topic
            }
            
            # Add domain filters if provided
            if request.include_domains:
                search_params["include_domains"] = request.include_domains
            if request.exclude_domains:
                search_params["exclude_domains"] = request.exclude_domains
            
            # Perform search using Tavily
            response = tavily_client.search(**search_params)
            
            # Process images
            images = []
            if "images" in response and response["images"]:
                for image in response["images"]:
                    if isinstance(image, dict):
                        # Image with description
                        images.append(ImageResult(
                            url=image.get("url", ""),
                            description=image.get("description", "")
                        ))
                    else:
                        # Simple image URL
                        images.append(ImageResult(url=image))
            
            # Process search results
            results = []
            if "results" in response and response["results"]:
                for result in response["results"]:
                    results.append(SearchResult(
                        title=result.get("title", ""),
                        url=result.get("url", ""),
                        content=result.get("content", ""),
                        score=result.get("score", 0.0)
                    ))
            
            return ImageSearchResponse(
                query=response.get("query", request.query),
                images=images,
                results=results,
                response_time=response.get("response_time", 0.0),
                total_images=len(images),
                total_results=len(results)
            )
            
        except Exception as e:
            print(f"[IMAGE_SEARCH] ❌ Error searching images: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error searching images: {str(e)}")
            
    except HTTPException as auth_error:
        print(f"[IMAGE_SEARCH] ❌ HTTP exception during authentication: {str(auth_error)}")
        raise auth_error
    except Exception as auth_error:
        print(f"[IMAGE_SEARCH] ❌ Unexpected error during authentication: {str(auth_error)}")
        raise HTTPException(status_code=401, detail="Authentication failed")

@router.get("/search", response_model=ImageSearchResponse)
async def search_images_simple(
    query: str = Query(..., description="Search query for images", example="medical histology"),
    max_results: int = Query(5, description="Maximum number of results", ge=1, le=20),
    search_depth: str = Query("advanced", description="Search depth: basic or advanced"),
    include_descriptions: bool = Query(True, description="Include image descriptions"),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Simple image search endpoint with query parameters.
    
    Args:
        query (str): The search query
        max_results (int): Maximum number of results (1-20)
        search_depth (str): Search depth - "basic" or "advanced"
        include_descriptions (bool): Whether to include AI-generated image descriptions
        
    Returns:
        ImageSearchResponse: Search results with images and descriptions
    """
    request = ImageSearchRequest(
        query=query,
        max_results=max_results,
        search_depth=search_depth,
        include_image_descriptions=include_descriptions
    )
    
    return await search_images_with_descriptions(request, credentials)

@router.get("/search_medical_images/", response_model=ImageSearchResponse)
async def search_medical_images(
    query: str = Query(..., description="Medical image search query", example="Histopathological examination shows IgA deposits"),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Search for medical images with medical domain filtering.
    
    Args:
        query (str): The medical image search query
        
    Returns:
        ImageSearchResponse: Medical images and related content
    """
    print(f"[IMAGE_SEARCH] 🔍 Medical image search with query: {query}")
    
    # Medical domains to prioritize
    medical_domains = [
        "nih.gov", 
        "pubmed.ncbi.nlm.nih.gov", 
        "medlineplus.gov", 
        "mayoclinic.org",
        "who.int",
        "cdc.gov",
        "nejm.org",
        "thelancet.com",
        "nature.com",
        "science.org"
    ]
    
    request = ImageSearchRequest(
        query=f"{query} medical images",
        max_results=10,
        search_depth="advanced",
        include_image_descriptions=True,
        include_domains=medical_domains,
        topic="general"
    )
    
    return await search_images_with_descriptions(request, credentials) 
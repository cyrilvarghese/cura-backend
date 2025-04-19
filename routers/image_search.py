from typing import List, Dict
from fastapi import APIRouter, HTTPException, Query
from langchain_community.retrievers import TavilySearchAPIRetriever
from pydantic import BaseModel
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

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
    query: str = Query(..., description="Medical image search query", example="Histopathological examination shows IgA deposits")
):
    """
    Search for medical images based on a query using Tavily.
    
    Args:
        query (str): The medical image search query
        
    Returns:
        ImageSearchResponse: List of images with their URLs, titles, and sources
    """
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
        print(f"❌ Error in search_medical_images: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) 
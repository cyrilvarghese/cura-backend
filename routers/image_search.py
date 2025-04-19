from typing import List, Dict
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
import os
from dotenv import load_dotenv
from tavily import TavilyClient
from crawl4ai import AsyncWebCrawler
import asyncio
import urllib.parse

# Load environment variables
load_dotenv()

# Initialize router and client
router = APIRouter(prefix="/image-search", tags=["image-search"])
tavily_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

class ImageSearchResponse(BaseModel):
    images: List[Dict[str, str]]

async def extract_images_from_url(url: str) -> List[Dict[str, str]]:
    """Extract images from a URL using Crawl4AI"""
    try:
        async with AsyncWebCrawler() as crawler:
            # Configure crawler to focus on images
            result = await crawler.arun(
                url=url,
                extract_images=True,  # Enable image extraction
                lazy_load_scroll=True,  # Handle lazy-loaded images
                timeout=30  # Add timeout to prevent hanging
            )
            
            # Get images from the crawl result - fix according to Crawl4AI documentation
            images = []
            # The media dictionary contains "images" key according to the docs
            if "images" in result.media:
                for image in result.media["images"]:
                    image_src = image.get("src", "")
                    
                    # Extract the actual image URL from Next.js image URLs
                    if "/_next/image?url=" in image_src:
                        # Parse the URL to extract the 'url' query parameter
                        try:
                            parsed_url = urllib.parse.urlparse(image_src)
                            query_params = urllib.parse.parse_qs(parsed_url.query)
                            if "url" in query_params and query_params["url"]:
                                image_src = query_params["url"][0]
                        except Exception as e:
                            print(f"Error parsing Next.js image URL: {e}")
                    
                    # More flexible image filtering
                    if any(domain in image_src for domain in ["cloudfront.net", "webpathology.com"]):
                        # Convert all values to strings to match Pydantic model
                        width = str(image.get("width", "")) if image.get("width") is not None else ""
                        height = str(image.get("height", "")) if image.get("height") is not None else ""
                        score = str(image.get("score", "0")) if image.get("score") is not None else "0"
                        
                        # Add more metadata if available
                        images.append({
                            "url": image_src,
                            "title": image.get("alt", "") or image.get("title", "") or "",
                            "source": url,  # Track source URL
                            "width": width,
                            "height": height,
                            "score": score
                        })
            return images
    except Exception as e:
        print(f"Error crawling {url}: {e}")
        return []

@router.get("/search_medical_images/", response_model=ImageSearchResponse)
async def search_medical_images(
    query: str = Query(..., description="Medical image search query", example="Leprosy histopathology"),
    max_results: int = Query(50, description="Maximum number of images to return"),
    include_domains: List[str] = Query(["webpathology.com"], description="Domains to include in search")
):
    """Search for medical images using Tavily for search and Crawl4AI for extraction"""
    try:
        # Step 1: Get URLs from Tavily
        search_response = tavily_client.search(
            query=f"{query} site:{' OR site:'.join(include_domains)}",
            search_depth="advanced",
            include_domains=include_domains,
            unique_results=True,
            max_results=5
        )
        
        print(f"Initial Search Response for '{query}':", search_response)
        
        # Get relevant URLs
        urls = [
            result["url"] 
            for result in search_response.get("results", [])
            if any(domain in result.get("url", "") for domain in include_domains)
        ]

        if not urls:
            return ImageSearchResponse(images=[])

        # Step 2: Extract images from each URL using Crawl4AI
        all_images = []
        seen_urls = set()
        
        # Process URLs concurrently
        tasks = [extract_images_from_url(url) for url in urls]
        results = await asyncio.gather(*tasks)
        
        # Combine results and deduplicate
        for images in results:
            for image in images:
                if image["url"] not in seen_urls:
                    seen_urls.add(image["url"])
                    all_images.append(image)
        
        print("\nExtracted Images:", all_images)
        return ImageSearchResponse(images=all_images[:max_results])
        
    except Exception as e:
        print(f"❌ Error in search_medical_images: {str(e)}")
        print(f"Error type: {type(e)}")
        print(f"Full error details: {repr(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Search failed: {str(e)}"
        ) 
"""
Test script for the Image Search API using Tavily

This script demonstrates how to use the image search endpoints:
1. Simple GET endpoint with query parameters
2. Advanced POST endpoint with full configuration
3. Medical-specific image search endpoint

Before running this script:
1. Make sure you have TAVILY_API_KEY set in your environment
2. Start your FastAPI server: uvicorn main:app --reload
3. Get an authentication token from your auth system
"""

import requests
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
BASE_URL = "http://localhost:8000"
AUTH_TOKEN = "your_jwt_token_here"  # Replace with actual token

headers = {
    "Authorization": f"Bearer {AUTH_TOKEN}",
    "Content-Type": "application/json"
}

def test_simple_image_search():
    """Test the simple GET endpoint for image search"""
    print("🔍 Testing Simple Image Search...")
    
    params = {
        "query": "medical histology",
        "max_results": 3,
        "search_depth": "advanced", 
        "include_descriptions": True
    }
    
    response = requests.get(
        f"{BASE_URL}/image-search/search",
        params=params,
        headers=headers
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Found {data['total_images']} images")
        print(f"📊 Response time: {data['response_time']:.2f}s")
        
        # Show first image
        if data['images']:
            first_image = data['images'][0]
            print(f"🖼️  First image: {first_image['url']}")
            if first_image.get('description'):
                print(f"📝 Description: {first_image['description'][:100]}...")
    else:
        print(f"❌ Error: {response.status_code} - {response.text}")

def test_advanced_image_search():
    """Test the advanced POST endpoint with full configuration"""
    print("\n🚀 Testing Advanced Image Search...")
    
    payload = {
        "query": "brain MRI scan",
        "max_results": 5,
        "search_depth": "advanced",
        "include_image_descriptions": True,
        "include_domains": ["nih.gov", "pubmed.ncbi.nlm.nih.gov"],
        "topic": "general"
    }
    
    response = requests.post(
        f"{BASE_URL}/image-search/search",
        json=payload,
        headers=headers
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Found {data['total_images']} images and {data['total_results']} related articles")
        print(f"📊 Response time: {data['response_time']:.2f}s")
        
        # Show images with descriptions
        for i, image in enumerate(data['images'][:2]):
            print(f"🖼️  Image {i+1}: {image['url']}")
            if image.get('description'):
                print(f"📝 Description: {image['description']}")
        
        # Show search results
        if data['results']:
            print(f"📄 First article: {data['results'][0]['title']}")
            print(f"🔗 URL: {data['results'][0]['url']}")
    else:
        print(f"❌ Error: {response.status_code} - {response.text}")

def test_medical_image_search():
    """Test the medical-specific image search endpoint"""
    print("\n🏥 Testing Medical Image Search...")
    
    params = {
        "query": "Histopathological examination shows IgA deposits"
    }
    
    response = requests.get(
        f"{BASE_URL}/image-search/search_medical_images/",
        params=params,
        headers=headers
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Found {data['total_images']} medical images")
        print(f"📊 Response time: {data['response_time']:.2f}s")
        
        # Show medical images
        for i, image in enumerate(data['images'][:3]):
            print(f"🩺 Medical Image {i+1}: {image['url']}")
            if image.get('description'):
                print(f"📝 Description: {image['description'][:150]}...")
                
        # Show related medical articles
        for i, result in enumerate(data['results'][:2]):
            print(f"📚 Medical Article {i+1}: {result['title']}")
            print(f"⭐ Relevance Score: {result['score']:.2f}")
    else:
        print(f"❌ Error: {response.status_code} - {response.text}")

def display_api_info():
    """Display information about the API endpoints"""
    print("📋 Image Search API Endpoints:")
    print("="*50)
    print("1. GET /image-search/search")
    print("   - Simple search with query parameters")
    print("   - Parameters: query, max_results, search_depth, include_descriptions")
    print()
    print("2. POST /image-search/search") 
    print("   - Advanced search with full configuration")
    print("   - Body: JSON with query, filters, and options")
    print()
    print("3. GET /image-search/search_medical_images/")
    print("   - Medical-specific search with domain filtering")
    print("   - Focuses on medical and scientific sources")
    print()
    print("🔑 Authentication: Bearer token required")
    print("🌐 Base URL: http://localhost:8000")
    print()

if __name__ == "__main__":
    print("🚀 Image Search API Test Suite")
    print("="*40)
    
    # Check if token is set
    if AUTH_TOKEN == "your_jwt_token_here":
        print("⚠️  Please set your AUTH_TOKEN in the script before running tests")
        print("💡 You can get a token by authenticating with your API")
        display_api_info()
        exit(1)
    
    # Check if Tavily API key is set
    if not os.getenv("TAVILY_API_KEY"):
        print("⚠️  TAVILY_API_KEY not found in environment variables")
        print("💡 Please add TAVILY_API_KEY to your .env file")
        exit(1)
    
    try:
        # Run tests
        test_simple_image_search()
        test_advanced_image_search()
        test_medical_image_search()
        
        print("\n✅ All tests completed!")
        
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to the API server")
        print("💡 Make sure your FastAPI server is running: uvicorn main:app --reload")
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
    
    print("\n" + "="*40)
    display_api_info() 
from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from datetime import datetime
from pathlib import Path
import json
import os
import google.generativeai as genai
import asyncio
from typing import List, Dict, Any, Optional
from tavily import TavilyClient
from serpapi import GoogleSearch
from utils.text_cleaner import clean_code_block
from auth.auth_api import get_user_from_token
from routers.case_creator.upload_test_image import TestType
import traceback

# Define the security scheme
security = HTTPBearer()

# Initialize the router
router = APIRouter(
    prefix="/intelligent-image-search",
    tags=["intelligent-image-search"]
)

# Initialize Gemini client
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

# Initialize Tavily client
tavily_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

# Response models
class ImageResult(BaseModel):
    url: str
    description: Optional[str] = None

class SearchResult(BaseModel):
    title: str
    url: str
    content: str
    score: float

class IntelligentImageSearchResponse(BaseModel):
    case_id: str
    test_name: str
    test_type: str
    primary_diagnosis: str
    generated_query: str
    search_context: str
    images: List[ImageResult]
    results: List[SearchResult]
    response_time: float
    total_images: int
    total_results: int
    processing_metadata: Dict[str, Any]

class IntelligentSearchRequest(BaseModel):
    case_id: str
    test_type: TestType
    test_name: str
    max_results: Optional[int] = 30
    search_depth: Optional[str] = "advanced"
    search_query: Optional[str] = None
    single_search: Optional[bool] = False  # Flag to use single search with more results instead of parallel searches

# Prompt for generating intelligent search queries
INTELLIGENT_SEARCH_PROMPT = """
You are a medical imaging search expert. Your task is to generate the most effective search query for finding relevant medical images based on a patient's diagnosis and the specific test being performed.

**Context:**
- Primary Diagnosis: {primary_diagnosis}
- Test Type: {test_type}
- Test Name: {test_name}

**Instructions:**
Generate a comprehensive and specific search query that will find the most relevant medical images. Consider:

1. **For Physical Exams:** Look for clinical presentations, physical signs, skin manifestations, or anatomical findings
2. **For Lab Tests:** Look for histopathology slides, microscopic findings, laboratory specimens, or diagnostic imaging

**Guidelines:**
- Use precise medical terminology
- Include both the condition name and relevant visual characteristics
- Consider synonyms and alternative terms for the condition
- Focus on what would be visually observable in the specified test type
- Avoid overly broad or generic terms
- Generate 2 diverse alternative queries with different medical terminology and perspectives

**Output Format:**
Provide a JSON response with the following structure:
```json
{{
  "search_query": "specific and targeted search query here",
  "search_context": "explanation of what type of images this query is designed to find",
  "medical_keywords": ["keyword1", "keyword2", "keyword3"],
  "alternative_contexts": [
    "descriptive context 1 for finding similar images",
    "descriptive context 2 with different medical terminology"
  ]
}}
```

**Example:**
For diagnosis "Primary genital herpes simplex virus infection (HSV-2)" and test "Vulvar exam":
```json
{{
  "search_query": "genital herpes HSV-2 vulvar lesions vesicles ulcers clinical presentation",
  "search_context": "Clinical images showing the characteristic vesicular and ulcerative lesions of genital herpes on vulvar tissue",
  "medical_keywords": ["herpes simplex", "vulvar vesicles", "genital ulcers", "HSV-2 lesions"],
      "alternative_contexts": [
      "Medical photographs showing herpes genitalis with vulvar involvement and clinical findings",
      "Dermatological images of HSV genital outbreak during vulvar examination"
    ]
}}
```

Now generate the search query for the given diagnosis and test:
"""

async def load_diagnosis_context(case_id: str) -> Dict[str, Any]:
    """Load the diagnosis context for the specified case."""
    try:
        file_path = Path(f"case-data/case{case_id}/diagnosis_context.json")
        if not file_path.exists():
            raise FileNotFoundError(f"Diagnosis context not found for case {case_id}")
        
        with open(file_path, 'r') as file:
            return json.load(file)
    except Exception as e:
        raise HTTPException(
            status_code=404, 
            detail=f"Failed to load diagnosis context for case {case_id}: {str(e)}"
        )

async def generate_intelligent_query(primary_diagnosis: str, test_type: str, test_name: str) -> Dict[str, Any]:
    """Generate an intelligent search query using Gemini."""
    try:
        # Configure the model
        model = genai.GenerativeModel('gemini-2.0-flash')
        generation_config = {
            "temperature": 0.3,  # Lower temperature for more focused results
            "top_p": 0.8,
            "top_k": 40
        }
        
        # Format the prompt
        formatted_prompt = INTELLIGENT_SEARCH_PROMPT.format(
            primary_diagnosis=primary_diagnosis,
            test_type=test_type,
            test_name=test_name
        )
        
        # Generate the query
        print(f"[INTELLIGENT_SEARCH] 🧠 Generating query with Gemini for: {test_name}")
        response = await asyncio.to_thread(
            model.generate_content,
            formatted_prompt,
            generation_config=generation_config
        )
        
        # Parse the response
        response_content = response.text
        print(f"[DEBUG] Gemini response: {response_content[:200]}...")
        
        # Clean and parse JSON
        cleaned_content = clean_code_block(response_content)
        query_data = json.loads(cleaned_content)
        
        return query_data
        
    except Exception as e:
        print(f"[ERROR] Failed to generate intelligent query: {str(e)}")
        # Fallback to basic query
        return {
            "search_query": f"{primary_diagnosis} {test_name} medical images",
            "search_context": f"Medical images related to {primary_diagnosis} and {test_name}",
            "medical_keywords": [primary_diagnosis, test_name],
            "alternative_contexts": [f"Clinical images showing {primary_diagnosis} medical presentation"]
        }

@router.post("/search", response_model=IntelligentImageSearchResponse)
async def intelligent_image_search(
    request: IntelligentSearchRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Perform intelligent image search based on case diagnosis and test information.
    
    Uses Gemini AI to generate contextually appropriate search queries and Tavily to find relevant medical images.
    """
    print(f"[INTELLIGENT_SEARCH] 🔍 Starting intelligent search for case {request.case_id}, test: {request.test_name}")
    
    # Extract token and authenticate the user
    try:
        token = credentials.credentials
        print(f"[DEBUG] Extracted JWT: {token}")
        
        print(f"[INTELLIGENT_SEARCH] 🔐 Authenticating user...")
        user_response = await get_user_from_token(token)
        if not user_response["success"]:
            error_message = user_response.get("error", "Authentication required")
            print(f"[INTELLIGENT_SEARCH] ❌ Authentication failed: {error_message}")
            raise HTTPException(status_code=401, detail=error_message)
        
        user_id = user_response["user"]["id"]
        print(f"[INTELLIGENT_SEARCH] ✅ User authenticated successfully. User ID: {user_id}")
        
        start_time = datetime.now()
        
        try:
            # Step 1: Load diagnosis context
            print(f"[INTELLIGENT_SEARCH] 📋 Loading diagnosis context for case {request.case_id}")
            diagnosis_context = await load_diagnosis_context(request.case_id)
            primary_diagnosis = diagnosis_context.get("primaryDiagnosis", "Unknown diagnosis")
            
            # Step 2: Use provided query or generate intelligent search query using Gemini
            if request.search_query:
                print(f"[INTELLIGENT_SEARCH] 📝 Using provided search query: {request.search_query}")
                main_query = request.search_query
                search_context = f"Custom search query provided by user for {request.test_name}"
                query_data = {
                    "search_query": main_query,
                    "search_context": search_context,
                    "medical_keywords": [primary_diagnosis, request.test_name],
                    "alternative_contexts": [],
                    "query_source": "user_provided"
                }
            else:
                print(f"[INTELLIGENT_SEARCH] 🧠 Generating intelligent query...")
                query_data = await generate_intelligent_query(
                    primary_diagnosis=primary_diagnosis,
                    test_type=request.test_type.value,
                    test_name=request.test_name
                )
                query_data["query_source"] = "ai_generated"
                
                # Use search_context as main query since it's more descriptive and natural
                main_query = query_data.get("search_context", query_data.get("search_query", ""))
                search_context = query_data.get("search_context", "")
                
                # Store original keyword query for metadata
                original_keyword_query = query_data.get("search_query", "")
                query_data["original_keyword_query"] = original_keyword_query
                
                print(f"[INTELLIGENT_SEARCH] 💡 Using descriptive context as query: {main_query[:100]}...")
            
            # Step 3: Perform Tavily search without domain restrictions
            print(f"[INTELLIGENT_SEARCH] 🔎 Searching with query: {main_query}")
            
            # Prepare search parameters - no domain restrictions for broader results
            search_params = {
                "query": main_query,
                "max_results": request.max_results,
                "search_depth": request.search_depth,
                "include_images": True,
                "include_image_descriptions": True,
                "topic": "general"
            }
            
            # Step 3: Run parallel searches if we have alternative queries (for AI-generated queries only)
            all_search_tasks = []
            all_queries_used = [main_query]
            
            if query_data.get("alternative_contexts") and not request.search_query:
                # Prepare all queries (main + 2 alternative contexts)
                all_queries = [main_query] + query_data.get("alternative_contexts", [])[:2]
                all_queries_used = all_queries
                
                print(f"[INTELLIGENT_SEARCH] 🚀 Running {len(all_queries)} parallel searches for optimal speed and coverage")
                
                # Create search tasks for parallel execution
                for i, query in enumerate(all_queries):
                    search_params_copy = search_params.copy()
                    search_params_copy["query"] = query
                    search_params_copy["max_results"] = 15 if i == 0 else 10  # Main query gets more sources
                    
                    async def search_with_query(params):
                        try:
                            return tavily_client.search(**params)
                        except Exception as e:
                            print(f"[WARNING] Search failed for query '{params['query']}': {str(e)}")
                            return {"images": [], "results": []}
                    
                    all_search_tasks.append(search_with_query(search_params_copy))
                
                # Execute all searches in parallel
                print(f"[INTELLIGENT_SEARCH] ⚡ Executing {len(all_search_tasks)} searches in parallel...")
                all_responses = await asyncio.gather(*all_search_tasks, return_exceptions=True)
                
            else:
                # Single search for user-provided queries
                search_params["max_results"] = request.max_results
                tavily_response = tavily_client.search(**search_params)
                all_responses = [tavily_response]
            
            # Aggregate and deduplicate results
            all_images = []
            all_results = []
            seen_image_urls = set()
            seen_result_urls = set()
            
            print(f"[INTELLIGENT_SEARCH] 📊 Processing {len(all_responses)} search responses...")
            
            for response in all_responses:
                if isinstance(response, Exception):
                    continue
                    
                # Process images with deduplication
                if "images" in response and response["images"]:
                    for image in response["images"]:
                        if isinstance(image, dict):
                            img_url = image.get("url", "")
                            if img_url and img_url not in seen_image_urls:
                                all_images.append(ImageResult(
                                    url=img_url,
                                    description=image.get("description", "")
                                ))
                                seen_image_urls.add(img_url)
                        else:
                            if image and image not in seen_image_urls:
                                all_images.append(ImageResult(url=image))
                                seen_image_urls.add(image)
                
                # Process results with deduplication
                if "results" in response and response["results"]:
                    for result in response["results"]:
                        result_url = result.get("url", "")
                        if result_url and result_url not in seen_result_urls:
                            all_results.append(SearchResult(
                                title=result.get("title", ""),
                                url=result_url,
                                content=result.get("content", ""),
                                score=result.get("score", 0.0)
                            ))
                            seen_result_urls.add(result_url)
            
            # Sort results by score and limit to requested amount  
            all_results.sort(key=lambda x: x.score, reverse=True)
            images = all_images[:request.max_results]  # User-requested image limit
            results = all_results[:10]  # Limit results to top 10 articles
            
            # Images and results are already processed above
            
            end_time = datetime.now()
            processing_time = (end_time - start_time).total_seconds()
            
            # Calculate average response time from all searches
            total_response_time = 0.0
            valid_responses = 0
            for response in all_responses:
                if not isinstance(response, Exception) and "response_time" in response:
                    total_response_time += float(response.get("response_time", 0.0))
                    valid_responses += 1
            
            avg_response_time = total_response_time / valid_responses if valid_responses > 0 else 0.0
            
            # Step 6: Prepare comprehensive response
            response_data = IntelligentImageSearchResponse(
                case_id=request.case_id,
                test_name=request.test_name,
                test_type=request.test_type.value,
                primary_diagnosis=primary_diagnosis,
                generated_query=main_query,
                search_context=search_context,
                images=images,
                results=results,
                response_time=avg_response_time,
                total_images=len(images),
                total_results=len(results),
                processing_metadata={
                    "total_processing_time": processing_time,
                    "medical_keywords": query_data.get("medical_keywords", []),
                    "alternative_contexts": query_data.get("alternative_contexts", []),
                    "original_keyword_query": query_data.get("original_keyword_query", ""),
                    "queries_used": all_queries_used,
                    "parallel_searches": len(all_queries_used) if not request.search_query else 1,
                    "domain_restrictions": "none",
                    "gemini_model": "gemini-2.0-flash",
                    "tavily_search_depth": request.search_depth,
                    "deduplication_stats": {
                        "unique_images": len(seen_image_urls),
                        "unique_results": len(seen_result_urls)
                    }
                }
            )
            
            print(f"[INTELLIGENT_SEARCH] ✅ Search completed successfully. Found {len(images)} images, {len(results)} articles")
            return response_data
        
        except Exception as e:
            print(f"[INTELLIGENT_SEARCH] ❌ Error during search: {str(e)}")
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Error during intelligent search: {str(e)}")
            
    except HTTPException as auth_error:
        print(f"[INTELLIGENT_SEARCH] ❌ HTTP exception during authentication: {str(auth_error)}")
        raise auth_error
    except Exception as auth_error:
        print(f"[INTELLIGENT_SEARCH] ❌ Unexpected error during authentication: {str(auth_error)}")
        raise HTTPException(status_code=401, detail="Authentication failed")

@router.post("/search-stream")
async def intelligent_image_search_stream(
    request: IntelligentSearchRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Stream intelligent image search results as they become available.
    Returns results one by one as each search completes.
    """
    print(f"[INTELLIGENT_SEARCH_STREAM] 🔍 Starting streaming search for case {request.case_id}, test: {request.test_name}")
    
    # Authenticate user (same as main endpoint)
    try:
        token = credentials.credentials
        user_response = await get_user_from_token(token)
        if not user_response["success"]:
            raise HTTPException(status_code=401, detail="Authentication required")
        
        user_id = user_response["user"]["id"]
        print(f"[INTELLIGENT_SEARCH_STREAM] ✅ User authenticated successfully. User ID: {user_id}")
        
        async def generate_streaming_results():
            try:
                # Step 1: Load diagnosis context
                diagnosis_context = await load_diagnosis_context(request.case_id)
                primary_diagnosis = diagnosis_context.get("primaryDiagnosis", "Unknown diagnosis")
                
                # Step 2: Generate queries
                if request.search_query:
                    main_query = request.search_query
                    search_context = f"Custom search query provided by user for {request.test_name}"
                    query_data = {"alternative_contexts": [], "query_source": "user_provided"}
                else:
                    query_data = await generate_intelligent_query(
                        primary_diagnosis=primary_diagnosis,
                        test_type=request.test_type.value,
                        test_name=request.test_name
                    )
                    main_query = query_data.get("search_context", query_data.get("search_query", ""))
                    search_context = query_data.get("search_context", "")
                
                # Step 3: Setup search parameters
                search_params = {
                    "max_results": request.max_results if request.search_query else 15,
                    "search_depth": request.search_depth,
                    "include_images": True,
                    "include_image_descriptions": True,
                    "topic": "general"
                }
                
                # Step 4: Execute searches sequentially and stream results one by one
                if query_data.get("alternative_contexts") and not request.search_query:
                    all_queries = [main_query] + query_data.get("alternative_contexts", [])[:2]
                    
                    print(f"[STREAM] 🚀 Executing {len(all_queries)} searches sequentially...")
                    
                    for i, query in enumerate(all_queries):
                        search_params_copy = search_params.copy()
                        search_params_copy["query"] = query
                        search_params_copy["max_results"] = 15 if i == 0 else 10
                        
                        try:
                            print(f"[STREAM] 🔍 Starting search {i+1}/3: {query[:50]}...")
                            
                            # Execute single search
                            response = tavily_client.search(**search_params_copy)
                            
                            # Process images from this search
                            batch_images = []
                            if "images" in response and response["images"]:
                                for image in response["images"]:
                                    if isinstance(image, dict):
                                        batch_images.append({
                                            "url": image.get("url", ""),
                                            "description": image.get("description", "")
                                        })
                                    else:
                                        batch_images.append({"url": image, "description": None})
                            
                            print(f"[STREAM] ✅ Search {i+1} completed - Found {len(batch_images)} images")
                            
                            # Stream this batch immediately after completion
                            batch_result = {
                                "batch_number": i + 1,
                                "total_batches": len(all_queries),
                                "query_used": query,
                                "images": batch_images,
                                "batch_size": len(batch_images),
                                "is_final": i == len(all_queries) - 1,
                                "case_id": request.case_id,
                                "test_name": request.test_name,
                                "primary_diagnosis": primary_diagnosis,
                                "timestamp": datetime.now().isoformat()
                            }
                            
                            yield f"data: {json.dumps(batch_result)}\n\n"
                            
                        except Exception as e:
                            print(f"[STREAM] ❌ Search {i+1} failed: {str(e)}")
                            error_batch = {
                                "batch_number": i + 1,
                                "total_batches": len(all_queries),
                                "error": str(e),
                                "query_used": query,
                                "images": [],
                                "batch_size": 0,
                                "is_final": i == len(all_queries) - 1,
                                "case_id": request.case_id,
                                "test_name": request.test_name,
                                "primary_diagnosis": primary_diagnosis,
                                "timestamp": datetime.now().isoformat()
                            }
                            yield f"data: {json.dumps(error_batch)}\n\n"
                else:
                    # Single search for user-provided queries
                    print(f"[STREAM] 🔍 Executing single search: {main_query[:50]}...")
                    search_params["query"] = main_query
                    response = tavily_client.search(**search_params)
                    
                    batch_images = []
                    if "images" in response and response["images"]:
                        for image in response["images"]:
                            if isinstance(image, dict):
                                batch_images.append({
                                    "url": image.get("url", ""),
                                    "description": image.get("description", "")
                                })
                            else:
                                batch_images.append({"url": image, "description": None})
                    
                    print(f"[STREAM] ✅ Single search completed - Found {len(batch_images)} images")
                    
                    final_result = {
                        "batch_number": 1,
                        "total_batches": 1,
                        "query_used": main_query,
                        "images": batch_images,
                        "batch_size": len(batch_images),
                        "is_final": True,
                        "case_id": request.case_id,
                        "test_name": request.test_name,
                        "primary_diagnosis": primary_diagnosis,
                        "timestamp": datetime.now().isoformat()
                    }
                    
                    yield f"data: {json.dumps(final_result)}\n\n"
                    
            except Exception as e:
                error_result = {
                    "error": str(e),
                    "batch_number": 0,
                    "images": [],
                    "is_final": True
                }
                yield f"data: {json.dumps(error_result)}\n\n"
        
        return StreamingResponse(
            generate_streaming_results(),
            media_type="text/plain",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Streaming search failed: {str(e)}")

@router.post("/search-serpapi", response_model=IntelligentImageSearchResponse)
async def intelligent_image_search_serpapi(
    request: IntelligentSearchRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Perform intelligent image search using SerpApi's Google Images API instead of Tavily.
    
    Uses Gemini AI to generate contextually appropriate search queries and SerpApi to find relevant Google Images.
    """
    print(f"[SERPAPI_SEARCH] 🔍 Starting SerpApi search for case {request.case_id}, test: {request.test_name}")
    
    # Extract token and authenticate the user
    try:
        token = credentials.credentials
        print(f"[DEBUG] Extracted JWT: {token}")
        
        print(f"[SERPAPI_SEARCH] 🔐 Authenticating user...")
        user_response = await get_user_from_token(token)
        if not user_response["success"]:
            error_message = user_response.get("error", "Authentication required")
            print(f"[SERPAPI_SEARCH] ❌ Authentication failed: {error_message}")
            raise HTTPException(status_code=401, detail=error_message)
        
        user_id = user_response["user"]["id"]
        print(f"[SERPAPI_SEARCH] ✅ User authenticated successfully. User ID: {user_id}")
        
        start_time = datetime.now()
        
        try:
            # Step 1: Load diagnosis context
            print(f"[SERPAPI_SEARCH] 📋 Loading diagnosis context for case {request.case_id}")
            diagnosis_context = await load_diagnosis_context(request.case_id)
            primary_diagnosis = diagnosis_context.get("primaryDiagnosis", "Unknown diagnosis")
            
            # Step 2: Use provided query or generate intelligent search query using Gemini
            if request.search_query:
                print(f"[SERPAPI_SEARCH] 📝 Using provided search query: {request.search_query}")
                main_query = request.search_query
                search_context = f"Custom search query provided by user for {request.test_name}"
                query_data = {
                    "search_query": main_query,
                    "search_context": search_context,
                    "medical_keywords": [primary_diagnosis, request.test_name],
                    "alternative_contexts": [],
                    "query_source": "user_provided"
                }
            else:
                print(f"[SERPAPI_SEARCH] 🧠 Generating intelligent query...")
                query_data = await generate_intelligent_query(
                    primary_diagnosis=primary_diagnosis,
                    test_type=request.test_type.value,
                    test_name=request.test_name
                )
                query_data["query_source"] = "ai_generated"
                
                # Use search_context as main query since it's more descriptive and natural
                main_query = query_data.get("search_context", query_data.get("search_query", ""))
                search_context = query_data.get("search_context", "")
                
                # Store original keyword query for metadata
                original_keyword_query = query_data.get("search_query", "")
                query_data["original_keyword_query"] = original_keyword_query
                
                print(f"[SERPAPI_SEARCH] 💡 Using descriptive context as query: {main_query[:100]}...")
            
            # Step 3: Setup SerpApi search parameters for Google Images
            serpapi_key = os.getenv("SERPAPI_API_KEY")
            if not serpapi_key:
                raise HTTPException(status_code=500, detail="SERPAPI_API_KEY environment variable not set")
            
            # Prepare search parameters for Google Images
            search_params = {
                "q": main_query,
                "tbm": "isch",  # Google Images search
                "api_key": serpapi_key,
                "num": min(request.max_results, 100),  # SerpApi supports up to 100 results per request
                "safe": "active",  # Safe search for medical content
                "hl": "en",  # Language
                "gl": "us"  # Country
            }
            
            # Step 4: Execute searches - check single_search flag
            all_search_tasks = []
            all_queries_used = [main_query]
             
            if request.single_search or request.search_query:
                # Single search mode: Use main query with maximum results
                print(f"[SERPAPI_SEARCH] 🎯 Single search mode - Using main query with {request.max_results} results")
                search_params["num"] = min(request.max_results, 100)  # SerpApi max limit
                search = GoogleSearch(search_params)
                serpapi_response = await asyncio.to_thread(search.get_dict)
                all_responses = [serpapi_response]
                
            elif query_data.get("alternative_contexts"):
                # Parallel search mode: Use main + alternative queries
                all_queries = [main_query] + query_data.get("alternative_contexts", [])[:2]
                all_queries_used = all_queries
                
                print(f"[SERPAPI_SEARCH] 🚀 Parallel search mode - Running {len(all_queries)} SerpApi searches")
                
                # Create search tasks for parallel execution
                for i, query in enumerate(all_queries):
                    search_params_copy = search_params.copy()
                    search_params_copy["q"] = query
                    search_params_copy["num"] = min(20 if i == 0 else 15, request.max_results)  # Main query gets more results
                    
                    async def search_with_serpapi(params):
                        try:
                            # Execute SerpApi search in thread since it's synchronous
                            search = GoogleSearch(params)
                            return await asyncio.to_thread(search.get_dict)
                        except Exception as e:
                            print(f"[WARNING] SerpApi search failed for query '{params['q']}': {str(e)}")
                            return {"images_results": [], "error": str(e)}
                    
                    all_search_tasks.append(search_with_serpapi(search_params_copy))
                
                # Execute all searches in parallel
                print(f"[SERPAPI_SEARCH] ⚡ Executing {len(all_search_tasks)} SerpApi searches in parallel...")
                all_responses = await asyncio.gather(*all_search_tasks, return_exceptions=True)
                
            else:
                # Fallback: Single search for cases without alternatives
                search_params["num"] = min(request.max_results, 100)
                search = GoogleSearch(search_params)
                serpapi_response = await asyncio.to_thread(search.get_dict)
                all_responses = [serpapi_response]
            
            # Step 5: Process and aggregate SerpApi results
            all_images = []
            all_results = []
            seen_image_urls = set()
            seen_result_urls = set()
            
            print(f"[SERPAPI_SEARCH] 📊 Processing {len(all_responses)} SerpApi responses...")
            
            for response in all_responses:
                if isinstance(response, Exception):
                    print(f"[WARNING] Exception in SerpApi response: {str(response)}")
                    continue
                
                if response.get("error"):
                    print(f"[WARNING] SerpApi error: {response['error']}")
                    continue
                    
                # Process Google Images results from SerpApi
                if "images_results" in response and response["images_results"]:
                    for image in response["images_results"]:
                        img_url = image.get("original", image.get("thumbnail", ""))
                        if img_url and img_url not in seen_image_urls:
                            all_images.append(ImageResult(
                                url=img_url,
                                description=image.get("title", "")
                            ))
                            seen_image_urls.add(img_url)
                
                # Process related search results (if available)
                if "organic_results" in response and response["organic_results"]:
                    for result in response["organic_results"]:
                        result_url = result.get("link", "")
                        if result_url and result_url not in seen_result_urls:
                            all_results.append(SearchResult(
                                title=result.get("title", ""),
                                url=result_url,
                                content=result.get("snippet", ""),
                                score=1.0  # SerpApi doesn't provide scores, using default
                            ))
                            seen_result_urls.add(result_url)
            
            # Limit results to requested amounts
            images = all_images[:request.max_results]
            results = all_results[:10]  # Limit results to top 10 articles
            
            end_time = datetime.now()
            processing_time = (end_time - start_time).total_seconds()
            
            # Step 6: Prepare comprehensive response
            response_data = IntelligentImageSearchResponse(
                case_id=request.case_id,
                test_name=request.test_name,
                test_type=request.test_type.value,
                primary_diagnosis=primary_diagnosis,
                generated_query=main_query,
                search_context=search_context,
                images=images,
                results=results,
                response_time=processing_time,
                total_images=len(images),
                total_results=len(results),
                processing_metadata={
                    "total_processing_time": processing_time,
                    "medical_keywords": query_data.get("medical_keywords", []),
                    "alternative_contexts": query_data.get("alternative_contexts", []),
                    "original_keyword_query": query_data.get("original_keyword_query", ""),
                    "queries_used": all_queries_used,
                    "parallel_searches": len(all_queries_used) if not (request.search_query or request.single_search) else 1,
                    "search_mode": "single_search" if (request.single_search or request.search_query) else "parallel_search",
                    "search_engine": "google_images_serpapi",
                    "gemini_model": "gemini-2.0-flash",
                    "serpapi_safe_search": "active",
                    "deduplication_stats": {
                        "unique_images": len(seen_image_urls),
                        "unique_results": len(seen_result_urls)
                    }
                }
            )
            
            print(f"[SERPAPI_SEARCH] ✅ SerpApi search completed successfully. Found {len(images)} images, {len(results)} articles")
            return response_data
        
        except Exception as e:
            print(f"[SERPAPI_SEARCH] ❌ Error during search: {str(e)}")
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Error during SerpApi search: {str(e)}")
            
    except HTTPException as auth_error:
        print(f"[SERPAPI_SEARCH] ❌ HTTP exception during authentication: {str(auth_error)}")
        raise auth_error
    except Exception as auth_error:
        print(f"[SERPAPI_SEARCH] ❌ Unexpected error during authentication: {str(auth_error)}")
        raise HTTPException(status_code=401, detail="Authentication failed")

@router.post("/search-serpapi-stream")
async def intelligent_image_search_serpapi_stream(
    request: IntelligentSearchRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Stream intelligent image search results using SerpApi as they become available.
    Returns results one by one as each search completes.
    """
    print(f"[SERPAPI_SEARCH_STREAM] 🔍 Starting streaming SerpApi search for case {request.case_id}, test: {request.test_name}")
    
    # Authenticate user (same as main endpoint)
    try:
        token = credentials.credentials
        user_response = await get_user_from_token(token)
        if not user_response["success"]:
            raise HTTPException(status_code=401, detail="Authentication required")
        
        user_id = user_response["user"]["id"]
        print(f"[SERPAPI_SEARCH_STREAM] ✅ User authenticated successfully. User ID: {user_id}")
        
        async def generate_serpapi_streaming_results():
            try:
                # Step 1: Load diagnosis context
                diagnosis_context = await load_diagnosis_context(request.case_id)
                primary_diagnosis = diagnosis_context.get("primaryDiagnosis", "Unknown diagnosis")
                
                # Step 2: Generate queries
                if request.search_query:
                    main_query = request.search_query
                    search_context = f"Custom search query provided by user for {request.test_name}"
                    query_data = {"alternative_contexts": [], "query_source": "user_provided"}
                else:
                    query_data = await generate_intelligent_query(
                        primary_diagnosis=primary_diagnosis,
                        test_type=request.test_type.value,
                        test_name=request.test_name
                    )
                    main_query = query_data.get("search_context", query_data.get("search_query", ""))
                    search_context = query_data.get("search_context", "")
                
                # Step 3: Setup SerpApi parameters
                serpapi_key = os.getenv("SERPAPI_API_KEY")
                if not serpapi_key:
                    raise Exception("SERPAPI_API_KEY environment variable not set")
                
                search_params = {
                    "tbm": "isch",  # Google Images
                    "api_key": serpapi_key,
                    "safe": "active",
                    "hl": "en",
                    "gl": "us"
                }
                
                # Step 4: Execute searches sequentially and stream results one by one - check single_search flag
                if request.single_search or request.search_query:
                    # Single search mode for streaming
                    print(f"[SERPAPI_STREAM] 🎯 Single search mode - Using main query with {request.max_results} results")
                    search_params["q"] = main_query
                    search_params["num"] = min(request.max_results, 100)
                    
                    search = GoogleSearch(search_params)
                    response = await asyncio.to_thread(search.get_dict)
                    
                    batch_images = []
                    if "images_results" in response and response["images_results"]:
                        for image in response["images_results"]:
                            img_url = image.get("original", image.get("thumbnail", ""))
                            if img_url:
                                batch_images.append({
                                    "url": img_url,
                                    "description": image.get("title", "")
                                })
                    
                    print(f"[SERPAPI_STREAM] ✅ Single SerpApi search completed - Found {len(batch_images)} images")
                    
                    final_result = {
                        "batch_number": 1,
                        "total_batches": 1,
                        "query_used": main_query,
                        "images": batch_images,
                        "batch_size": len(batch_images),
                        "is_final": True,
                        "case_id": request.case_id,
                        "test_name": request.test_name,
                        "primary_diagnosis": primary_diagnosis,
                        "search_engine": "google_images_serpapi",
                        "search_mode": "single_search",
                        "timestamp": datetime.now().isoformat()
                    }
                    
                    yield f"data: {json.dumps(final_result)}\n\n"
                
                elif query_data.get("alternative_contexts"):
                    # Parallel search mode (sequential execution for streaming)
                    all_queries = [main_query] + query_data.get("alternative_contexts", [])[:2]
                    
                    print(f"[SERPAPI_STREAM] 🚀 Parallel search mode - Executing {len(all_queries)} SerpApi searches sequentially...")
                    
                    for i, query in enumerate(all_queries):
                        search_params_copy = search_params.copy()
                        search_params_copy["q"] = query
                        search_params_copy["num"] = min(20 if i == 0 else 15, request.max_results)
                        
                        try:
                            print(f"[SERPAPI_STREAM] 🔍 Starting SerpApi search {i+1}/3: {query[:50]}...")
                            
                            # Execute single SerpApi search
                            search = GoogleSearch(search_params_copy)
                            response = await asyncio.to_thread(search.get_dict)
                            
                            # Process images from this search
                            batch_images = []
                            if "images_results" in response and response["images_results"]:
                                for image in response["images_results"]:
                                    img_url = image.get("original", image.get("thumbnail", ""))
                                    if img_url:
                                        batch_images.append({
                                            "url": img_url,
                                            "description": image.get("title", "")
                                        })
                            
                            print(f"[SERPAPI_STREAM] ✅ SerpApi search {i+1} completed - Found {len(batch_images)} images")
                            
                            # Stream this batch immediately after completion
                            batch_result = {
                                "batch_number": i + 1,
                                "total_batches": len(all_queries),
                                "query_used": query,
                                "images": batch_images,
                                "batch_size": len(batch_images),
                                "is_final": i == len(all_queries) - 1,
                                "case_id": request.case_id,
                                "test_name": request.test_name,
                                "primary_diagnosis": primary_diagnosis,
                                "search_engine": "google_images_serpapi",
                                "timestamp": datetime.now().isoformat()
                            }
                            
                            yield f"data: {json.dumps(batch_result)}\n\n"
                            
                        except Exception as e:
                            print(f"[SERPAPI_STREAM] ❌ SerpApi search {i+1} failed: {str(e)}")
                            error_batch = {
                                "batch_number": i + 1,
                                "total_batches": len(all_queries),
                                "error": str(e),
                                "query_used": query,
                                "images": [],
                                "batch_size": 0,
                                "is_final": i == len(all_queries) - 1,
                                "case_id": request.case_id,
                                "test_name": request.test_name,
                                "primary_diagnosis": primary_diagnosis,
                                "search_engine": "google_images_serpapi",
                                "timestamp": datetime.now().isoformat()
                            }
                            yield f"data: {json.dumps(error_batch)}\n\n"
                else:
                    # Single search for user-provided queries
                    print(f"[SERPAPI_STREAM] 🔍 Executing single SerpApi search: {main_query[:50]}...")
                    search_params["q"] = main_query
                    search_params["num"] = min(request.max_results, 100)
                    
                    search = GoogleSearch(search_params)
                    response = await asyncio.to_thread(search.get_dict)
                    
                    batch_images = []
                    if "images_results" in response and response["images_results"]:
                        for image in response["images_results"]:
                            img_url = image.get("original", image.get("thumbnail", ""))
                            if img_url:
                                batch_images.append({
                                    "url": img_url,
                                    "description": image.get("title", "")
                                })
                    
                    print(f"[SERPAPI_STREAM] ✅ Single SerpApi search completed - Found {len(batch_images)} images")
                    
                    final_result = {
                        "batch_number": 1,
                        "total_batches": 1,
                        "query_used": main_query,
                        "images": batch_images,
                        "batch_size": len(batch_images),
                        "is_final": True,
                        "case_id": request.case_id,
                        "test_name": request.test_name,
                        "primary_diagnosis": primary_diagnosis,
                        "search_engine": "google_images_serpapi",
                        "timestamp": datetime.now().isoformat()
                    }
                    
                    yield f"data: {json.dumps(final_result)}\n\n"
                    
            except Exception as e:
                error_result = {
                    "error": str(e),
                    "batch_number": 0,
                    "images": [],
                    "is_final": True,
                    "search_engine": "google_images_serpapi"
                }
                yield f"data: {json.dumps(error_result)}\n\n"
        
        return StreamingResponse(
            generate_serpapi_streaming_results(),
            media_type="text/plain",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"SerpApi streaming search failed: {str(e)}")



 
import pytest
import asyncio
import time
from fastapi.testclient import TestClient
from routers.case_player.treatment_feedback_gemini import router

async def slow_operation(delay: float) -> float:
    """Simulates a slow operation and returns the time it took."""
    start_time = time.perf_counter()  # Use perf_counter for more precise timing
    await asyncio.sleep(delay)
    return time.perf_counter() - start_time

async def test_concurrent_operations():
    """Test if operations are truly running concurrently."""
    # Create three operations with different delays
    delays = [2.0, 2.0, 2.0]
    
    start_time = time.perf_counter()  # Use perf_counter for more precise timing
    
    # Run operations concurrently
    tasks = [slow_operation(delay) for delay in delays]
    results = await asyncio.gather(*tasks)
    
    total_time = time.perf_counter() - start_time
    sequential_time = sum(delays)
    expected_concurrent_time = max(delays)
    
    # Calculate efficiency metrics with safeguards
    efficiency = ((sequential_time - total_time) / sequential_time * 100) if sequential_time > 0 else 0
    overhead = max(0, total_time - expected_concurrent_time)  # Ensure non-negative overhead
    
    print("\n=== Async Performance Analysis ===")
    print(f"Total time taken: {total_time:.2f}s")
    print(f"If run sequentially: {sequential_time:.2f}s")
    print(f"Theoretical minimum: {expected_concurrent_time:.2f}s")
    print(f"Concurrency overhead: +{overhead:.2f}s")  # Added plus sign to indicate overhead
    print(f"\nEfficiency gained: {min(100, efficiency):.1f}%")  # Cap at 100%
    
    if efficiency > 60:
        print("\n✅ EXCELLENT! Your code is running highly concurrently!")
        print(f"You saved {min(100, efficiency):.1f}% of time compared to sequential execution.")
    elif efficiency > 40:
        print("\n✅ GOOD! Your code is running concurrently with moderate efficiency.")
        print("There might be some room for optimization.")
    elif efficiency > 20:
        print("\n⚠️ FAIR. Your code shows some concurrency but could be improved.")
        print("Consider checking for blocking operations.")
    else:
        print("\n❌ POOR. Your code is running almost sequentially.")
        print("Check for blocking operations or synchronous code in your async functions.")
    
    # Updated assertions with more lenient timing checks
    assert total_time < sequential_time, (
        f"Operations appear to be running sequentially. "
        f"Expected less than {sequential_time:.2f}s, got {total_time:.2f}s"
    )
    
    # Allow for some overhead in concurrent execution
    max_acceptable_time = expected_concurrent_time + 1.0
    assert total_time <= max_acceptable_time, (
        f"Operations took longer than acceptable. "
        f"Expected <= {max_acceptable_time:.2f}s, got {total_time:.2f}s"
    )

@pytest.mark.asyncio
async def test_multiple_api_calls():
    """Test concurrent API calls to your feedback endpoints."""
    # Create test data
    test_data = {
        "case_id": "16",
        "student_inputs_pre_treatment": ["test1", "test2", "test3"],
        "student_inputs_monitoring": ["monitor1", "monitor2", "monitor3"]
    }
    
    start_time = time.perf_counter()
    
    # Import the actual app instead of just the router
    from main import app  # Make sure to import your FastAPI app
    
    # Use TestClient in a way that actually tests the real endpoints
    client = TestClient(app)
    
    # Make multiple API calls in sequence to measure baseline
    sequential_start = time.perf_counter()
    
    response1 = client.post("/feedback/pre_treatment_gemini", json=test_data)
    response2 = client.post("/feedback/monitoring_gemini", json=test_data)
    response3 = client.post("/feedback/pre_treatment_gemini", json=test_data)
    
    sequential_time = time.perf_counter() - sequential_start
    
    # Now test concurrent behavior using asyncio and httpx for true async HTTP requests
    import httpx
    
    async_start = time.perf_counter()
    
    # Use httpx.AsyncClient for true asynchronous HTTP requests
    async with httpx.AsyncClient(app=app, base_url="http://test") as async_client:
        tasks = [
            async_client.post("/feedback/pre_treatment_gemini", json=test_data),
            async_client.post("/feedback/monitoring_gemini", json=test_data),
            async_client.post("/feedback/pre_treatment_gemini", json=test_data)
        ]
        
        responses = await asyncio.gather(*tasks)
    
    concurrent_time = time.perf_counter() - async_start
    
    # Calculate efficiency metrics
    efficiency = min(100, ((sequential_time - concurrent_time) / sequential_time * 100)) if sequential_time > 0 else 0
    
    print("\n=== API Concurrency Analysis ===")
    print(f"Sequential time for 3 API calls: {sequential_time:.2f}s")
    print(f"Concurrent time for 3 API calls: {concurrent_time:.2f}s")
    print(f"Efficiency gained: {efficiency:.1f}%")
    
    if efficiency > 60:
        print("\n✅ EXCELLENT! API endpoints are truly asynchronous!")
    elif efficiency > 40:
        print("\n✅ GOOD! API endpoints show good asynchronous behavior.")
    elif efficiency > 20:
        print("\n⚠️ FAIR. API endpoints show some asynchronicity but could be improved.")
    else:
        print("\n❌ POOR. API endpoints are running almost sequentially.")
        print("Check for blocking operations in your endpoint handlers.")
    
    # Verify all requests succeeded
    for response in responses:
        assert response.status_code == 200
    
    # Assert that concurrent execution is significantly faster
    assert concurrent_time < sequential_time * 0.7, (
        f"API endpoints don't appear to be truly asynchronous. "
        f"Expected concurrent time to be at least 30% faster than sequential time. "
        f"Sequential: {sequential_time:.2f}s, Concurrent: {concurrent_time:.2f}s"
    )

if __name__ == "__main__":
    asyncio.run(test_concurrent_operations()) 
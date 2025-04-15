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
    
    start_time = time.perf_counter()  # Use perf_counter for more precise timing
    
    # Make multiple concurrent API calls
    async with TestClient(router) as client:
        tasks = [
            client.post("/feedback/pre_treatment_gemini", json=test_data),
            client.post("/feedback/monitoring_gemini", json=test_data),
            client.post("/feedback/pre_treatment_gemini", json=test_data)
        ]
        
        responses = await asyncio.gather(*tasks)
    
    total_time = time.perf_counter() - start_time
    expected_sequential_time = 6.0  # Assuming each call takes ~2s
    
    # Calculate efficiency metrics with safeguards
    efficiency = min(100, ((expected_sequential_time - total_time) / expected_sequential_time * 100))
    
    print("\n=== API Concurrency Analysis ===")
    print(f"Total time for 3 API calls: {total_time:.2f}s")
    print(f"Expected sequential time: {expected_sequential_time:.2f}s")
    print(f"Efficiency gained: {efficiency:.1f}%")
    
    if efficiency > 60:
        print("\n✅ EXCELLENT! API calls are running highly concurrently!")
    elif efficiency > 40:
        print("\n✅ GOOD! API calls show good concurrent behavior.")
    elif efficiency > 20:
        print("\n⚠️ FAIR. API calls show some concurrency but could be improved.")
    else:
        print("\n❌ POOR. API calls are running almost sequentially.")
    
    # Verify all requests succeeded
    for response in responses:
        assert response.status_code == 200
    
    # Updated assertion with more realistic timing expectation
    assert total_time < expected_sequential_time, (
        f"API calls appear to be running sequentially. "
        f"Expected less than {expected_sequential_time:.2f}s, got {total_time:.2f}s"
    )

if __name__ == "__main__":
    asyncio.run(test_concurrent_operations()) 
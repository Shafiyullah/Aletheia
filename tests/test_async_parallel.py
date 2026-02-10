import asyncio
import time
from unittest.mock import MagicMock, AsyncMock, patch
from core.engine import AletheiaEngine
from core.safety import SecurityViolationException

async def test_parallel_execution():
    print("--- Testing Parallel Execution (Asyncio.gather) ---\n")
    
    engine = AletheiaEngine()
    engine.client = MagicMock()
    
    # Mock async responses
    mock_classify_response = MagicMock()
    mock_classify_response.text = "GENERAL_LOGIC"
    
    mock_security_response = MagicMock()
    mock_security_response.text = "SAFE"
    
    # Create async mock
    async def mock_generate(*args, **kwargs):
        # Simulate delay to test parallelization
        await asyncio.sleep(0.1)
        # Return different responses based on model
        if kwargs.get('model') == 'gemini-2.0-flash-exp':
            return mock_security_response
        return mock_classify_response
    
    engine.client.aio.models.generate_content = AsyncMock(side_effect=mock_generate)
    
    # Test 1: Verify parallel execution is faster
    print("Test 1: Measuring parallel execution time...")
    start = time.time()
    
    code = "print('hello')"
    result = await engine.dispatch_optimization(code)
    
    elapsed = time.time() - start
    print(f"Elapsed time: {elapsed:.2f}s")
    
    # With parallel execution, both tasks run concurrently (~0.1s)
    # Without it, they'd run sequentially (~0.2s)
    if elapsed < 0.15:
        print("PASS: Parallel execution confirmed (tasks ran concurrently)\n")
    else:
        print("FAIL: Tasks may have run sequentially\n")
    
    # Test 2: Security violation aborts optimization
    print("Test 2: Testing security violation handling...")
    
    async def mock_generate_block(*args, **kwargs):
        if kwargs.get('model') == 'gemini-2.0-flash-exp':
            block_response = MagicMock()
            block_response.text = "BLOCK"
            return block_response
        return mock_classify_response
    
    engine.client.aio.models.generate_content = AsyncMock(side_effect=mock_generate_block)
    
    result = await engine.dispatch_optimization("malicious_code()")
    
    if "error" in result.lower() or "violation" in result.lower():
        print("PASS: Security violation correctly aborted optimization\n")
    else:
        print(f"FAIL: Expected error response, got: {result}\n")
    
    print("All tests completed!")

if __name__ == "__main__":
    asyncio.run(test_parallel_execution())

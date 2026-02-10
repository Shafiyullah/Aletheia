import asyncio
import sys
import os
from unittest.mock import MagicMock, AsyncMock

# Add project root to sys.path
sys.path.append(os.getcwd())

from core.engine import AletheiaEngine

async def test_dispatch():
    print("Testing dispatch_optimization...", flush=True)
    engine = AletheiaEngine(api_key="fake_key_for_test")
    
    # Mock the client to avoid real API calls
    engine.client = MagicMock()
    engine.client.aio.models.generate_content = AsyncMock()

    # Mock the optimization methods to check routing
    # We need to attach these mocks to the instance
    engine.generate_jax_optimization = AsyncMock(return_value="# JAX Optimized")
    engine.generate_async_refactor = AsyncMock(return_value="# Async Refactored")

    # Test Case 1: HEAVY_MATH
    print("\nTest Case 1: HEAVY_MATH", flush=True)
    # Setup mock for classification
    mock_response_math = MagicMock()
    mock_response_math.text = "HEAVY_MATH"
    engine.client.aio.models.generate_content.return_value = mock_response_math

    result = await engine.dispatch_optimization("import numpy as np; ...")
    
    if result == "# JAX Optimized":
        print("PASS: HEAVY_MATH routed correctly.", flush=True)
    else:
        print(f"FAIL: HEAVY_MATH routed to {result}", flush=True)
        pass
        
    # Test Case 2: GENERAL_LOGIC
    print("\nTest Case 2: GENERAL_LOGIC", flush=True)
    # Setup mock for classification
    mock_response_general = MagicMock()
    mock_response_general.text = "GENERAL_LOGIC"
    engine.client.aio.models.generate_content.return_value = mock_response_general

    result = await engine.dispatch_optimization("def read_file(): ...")
    
    if result == "# Async Refactored":
        print("PASS: GENERAL_LOGIC routed correctly.", flush=True)
    else:
        print(f"FAIL: GENERAL_LOGIC routed to {result}", flush=True)

    # Test Case 3: Fallback (Math fails)
    print("\nTest Case 3: Fallback", flush=True)
    mock_response_math.text = "HEAVY_MATH"
    engine.client.aio.models.generate_content.return_value = mock_response_math
    
    # Make JAX fail
    engine.generate_jax_optimization.return_value = "# Error: JAX Failed"
    
    result = await engine.dispatch_optimization("import numpy as np; ...")
    
    if result == "# Async Refactored":
        print("PASS: Fallback to Async Refactor successful.", flush=True)
    else:
        print(f"FAIL: Fallback failed, got {result}", flush=True)

if __name__ == "__main__":
    asyncio.run(test_dispatch())

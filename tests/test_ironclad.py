import asyncio
import os
import json
from unittest.mock import MagicMock, patch
from core.engine import AletheiaEngine
from core.safety import ai_security_check, SecurityViolationException
from core.config import MODEL_FAST, MODEL_SMART

async def test_ironclad():
    print("--- Starting Operation Ironclad Verification ---")
    
    # 1. Test AI Sentinel
    print("\n[Testing AI Sentinel]")
    safe_code = "print('Hello World')"
    unsafe_code = "import os; os.system('rm -rf /')"
    
    # Mocking genai for safety check to avoid spending tokens/latency and ensure deterministic test
    # We will verify it calls the API. 
    # Actually, let's use the real API for this test if possible, but mocking is safer for CI/automated.
    # Given the instructions, I should probably try to respect the user's environment.
    # Let's try real API for safety check if key exists.
    
    if os.environ.get("GEMINI_API_KEY"):
        try:
            print("Testing Safe Code...")
            # Should not raise
            ai_security_check(safe_code)
            print("PASS: Safe code passed.")
            
            print("Testing Unsafe Code (Simulating Block)...")
            # We can't easily force the model to block "Hello World", but we can try a known bad pattern
            # Note: The model might allow checking "unsafe code" string unless checking it itself is unsafe.
            # Using a mock for the blocking case to be sure.
            with patch('google.genai.Client') as MockClient:
                mock_instance = MockClient.return_value
                # Mock response for unsafe code
                mock_response = MagicMock()
                mock_response.text = "BLOCK"
                mock_instance.models.generate_content.return_value = mock_response
                
                try:
                    ai_security_check(unsafe_code)
                    print("FAIL: Unsafe code should have raised SecurityViolationException.")
                except SecurityViolationException:
                    print("PASS: Unsafe code blocked.")
        except Exception as e:
            print(f"FAIL: Logic error in Sentinel: {e}")
    else:
        print("SKIP: No API Key.")

    # 2. Test SQL Optimization (Business Mode)
    print("\n[Testing Business Mode: SQL]")
    engine = AletheiaEngine()
    if engine.client:
        sql = "SELECT * FROM users WHERE id = 1"
        res = await engine.optimize_sql(sql)
        if "-- Error" not in res and "Gemini Client not initialized" not in res:
            print(f"PASS: SQL Optimized (Length: {len(res)})")
        else:
            print(f"FAIL: SQL Optimization Error: {res}")
    else:
        print("SKIP: Engine not initialized.")

    # 3. Test Graceful Fallback
    print("\n[Testing Graceful Fallback]")
    # We force JAX optimization to fail by mocking the internal call or using a bad model
    # We will assume AletheiaEngine is structure correctly.
    
    with patch.object(engine, 'generate_jax_optimization', side_effect=Exception("Simulated JAX Failure")) as mock_jax:
       # Wait, we need to mock the *internal* behavior of generate_jax_optimization if we want to test the try-except *inside* it.
       # But generate_jax_optimization is what we want to test.
       # So we need to mock the API call *inside* generate_jax_optimization to raise exception.
       
       pass 

    # Let's re-instantiate engine and mock the client
    engine_mock = AletheiaEngine()
    engine_mock.client = MagicMock()
    # Mock models.generate_content to raise Exception
    engine_mock.client.aio.models.generate_content.side_effect = Exception("API Down")
    
    from unittest.mock import AsyncMock
    # We also need to mock generate_async_refactor to return "Fallback Code"
    # It must be an awaitable
    engine_mock.generate_async_refactor = AsyncMock(return_value="print('Fallback Code')")
    
    print("Triggering JAX Optimization with broken API...")
    # Call the actual method we want to test
    # We need to ensure we call the mocked engine's method, not define a new one.
    # engine_mock is an instance of AletheiaEngine. generate_jax_optimization is an instance method.
    # We need to bind the method? No, Python methods are bound to instance.
    # But wait, we just instantiated AletheiaEngine.
    
    # Actually, we should redefine generate_jax_optimization on the instance? No, that's not how testing works usually.
    # We want to run the REAL generate_jax_optimization, but with mocked client and mocked generate_async_refactor.
    # engine_mock.generate_jax_optimization is the real method bound to engine_mock.
    
    res_json = await engine_mock.generate_jax_optimization("def foo(): pass")
    
    try:
        res = json.loads(res_json)
        if res.get("method") == "fallback" and res.get("code") == "print('Fallback Code')":
            print("PASS: Graceful Fallback triggered and returned correct JSON.")
        else:
            print(f"FAIL: Unexpected JSON response: {res}")
    except Exception as e:
        print(f"FAIL: Error parsing fallback response: {e}. Raw: {res_json}")

if __name__ == "__main__":
    asyncio.run(test_ironclad())

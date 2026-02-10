import asyncio
import os
from unittest.mock import MagicMock, patch
from core.engine import AletheiaEngine

async def test_sql_audit():
    print("--- Testing SQL Performance Audit ---")
    
    # We want to test that the prompt actually produces an audit.
    # Since we can't easily mock the exact model output without mocking the client deeply,
    # we will rely on a live call if possible, or a mocked call that returns checking logic.
    
    # Actually, for deterministic testing of the *code logic* (not the AI), we should mock the client
    # but verify the prompt sent contains the "Senior Database Administrator" instructions.
    
    engine = AletheiaEngine()
    engine.client = MagicMock()
    
    # Mock response
    mock_response = MagicMock()
    mock_response.text = """
    /* SQL PERFORMANCE AUDIT */
    /* 1. SELECT * detected. Replace with specific columns. */
    SELECT id, name FROM users;
    """
    engine.client.aio.models.generate_content.return_value = mock_response
    
    query = "SELECT * FROM users"
    result = await engine.optimize_sql(query)
    
    print(f"Mocked Audit Result:\n{result}")
    
    # Verify prompt contains DBA instructions
    call_args = engine.client.aio.models.generate_content.call_args
    if call_args:
        prompt_sent = call_args.kwargs['contents']
        if "Senior Database Administrator" in prompt_sent and "Flag `SELECT *`" in prompt_sent:
            print("PASS: Prompt contains DBA instructions.")
        else:
            print("FAIL: Prompt does not match DBA requirements.")
            print(f"Prompt sent: {prompt_sent}")
    else:
        print("FAIL: Client not called.")

if __name__ == "__main__":
    asyncio.run(test_sql_audit())

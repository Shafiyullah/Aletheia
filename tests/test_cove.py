import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock

# Add root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.veritas import VeritasAuditor

SOURCE_TEXT = "Mocked Text"

async def test_cove_mocked():
    print("--- Testing Chain-of-Verification (CoVe) [MOCKED] ---\n")
    
    auditor = VeritasAuditor(api_key="mock_key")
    
    # Mock the client
    mock_response = MagicMock()
    mock_response.text = """
    ```json
    {
        "step_1_draft": "Draft Answer",
        "step_2_verification_points": ["Fact 1"],
        "step_3_corrections": "None",
        "verdict": "TRUE",
        "confidence": 0.99,
        "reasoning": "The text explicitly states...",
        "citations": ["Quote"]
    }
    ```
    """
    
    # Mock nested async call: client.aio.models.generate_content
    auditor.client = MagicMock()
    auditor.client.aio = MagicMock()
    auditor.client.aio.models = MagicMock()
    auditor.client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    print("1. Testing Logic Flow (Mocked Response)...")
    result = await auditor.verify_claim_cove("Test Claim", SOURCE_TEXT)
    
    print(f"Verdict: {result.get('verdict')}")
    print(f"Confidence: {result.get('confidence')}")
    
    if result.get('verdict') == "TRUE" and result.get('confidence') == 0.99:
        print("\n✅ PASS: CoVe Logic correctly parses JSON response.")
    else:
        print("\n❌ FAIL: Parsing logic broken.")

if __name__ == "__main__":
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(test_cove_mocked())

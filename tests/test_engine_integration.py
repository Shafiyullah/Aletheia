import pytest
import json
from unittest.mock import MagicMock, patch, AsyncMock
from core.engine import AletheiaEngine

@pytest.fixture
def mock_genai_client():
    with patch("google.genai.Client") as mock:
        # returns an async mock for aio
        mock.return_value.aio.models.generate_content = AsyncMock()
        yield mock

@pytest.fixture
def engine(mock_genai_client):
    return AletheiaEngine(api_key="dummy_key")

@pytest.mark.asyncio
async def test_dispatch_math(engine):
    # Mock classification
    engine.client.aio.models.generate_content.side_effect = [
        MagicMock(text="HEAVY_MATH"), # Classification
        MagicMock(text=json.dumps({"method": "jax", "code": "import jax"})) # JAX Gen
    ]
    
    # Mock Security Check to pass (it runs in parallel)
    # Must patch core.safety.ai_security_check_async because core.engine imports it
    with patch("core.safety.ai_security_check_async", new_callable=AsyncMock) as mock_sec:
        result_json = await engine.dispatch_optimization("import numpy as np")
        
    result = json.loads(result_json)
    assert result["method"] == "jax"
    assert "jax" in result["code"]

@pytest.mark.asyncio
async def test_dispatch_sql(engine):
    # Mock classification
    engine.client.aio.models.generate_content.side_effect = [
       MagicMock(text="SQL"), # Classification
       MagicMock(text="SELECT * FROM optimized") # SQL Gen
    ]

    with patch("core.safety.ai_security_check_async", new_callable=AsyncMock):
        result_json = await engine.dispatch_optimization("SELECT * FROM users")

    result = json.loads(result_json)
    assert result["method"] == "sql_audit"
    assert "optimized" in result["code"]

@pytest.mark.asyncio
async def test_dispatch_general(engine):
    # Mock classification
    engine.client.aio.models.generate_content.side_effect = [
       MagicMock(text="GENERAL_LOGIC"), # Classification
       MagicMock(text="def optimized(): pass") # Async Gen
    ]

    with patch("core.safety.ai_security_check_async", new_callable=AsyncMock):
        result_json = await engine.dispatch_optimization("print('hello')")
    
    result = json.loads(result_json)
    assert result["method"] == "complexity_reducer"

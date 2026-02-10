import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock
from core.engine import AletheiaEngine
from core.veritas import VeritasAuditor

@pytest.mark.asyncio
async def test_jax_optimization_mock():
    engine = AletheiaEngine(api_key="fake_key")
    # Mock the client and model
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "```python\nimport jax.numpy as jnp\n@jax.jit\ndef opt(): pass\n```"
    
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)
    engine.client = mock_client
    
    result = await engine.generate_jax_optimization("def slow(): pass")
    assert "jax.jit" in result
    assert "jnp" in result

@pytest.mark.asyncio
async def test_audit_pdf_mock():
    auditor = VeritasAuditor(api_key="fake_key")
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = '[{"claim": "test claim", "citation": "test cite", "verification": "YES", "evidence": "test"}]'
    
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)
    auditor.client = mock_client
    
    result = await auditor.audit_pdf("some pdf text")
    assert len(result) == 1
    assert result[0]["claim"] == "test claim"

def test_blast_radius():
    engine = AletheiaEngine()
    files = {
        "main.py": "import utils",
        "utils.py": "def add(a, b): return a + b"
    }
    graph = engine.analyze_blast_radius(files)
    assert "utils.py" in graph.nodes
    assert "main.py" in graph.nodes
    # Dependency is utils -> main
    assert graph.has_edge("utils.py", "main.py")
    
    impacted = engine.get_impacted_files("utils.py")
    assert "main.py" in impacted

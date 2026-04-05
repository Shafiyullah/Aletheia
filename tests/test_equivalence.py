import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from core.engine import AletheiaEngine

@pytest.fixture
def mock_genai_client():
    with patch("google.genai.Client") as mock:
        mock.return_value.aio.models.generate_content = AsyncMock()
        yield mock

@pytest.fixture
def engine(mock_genai_client):
    return AletheiaEngine(api_key="dummy_key")

@pytest.mark.asyncio
async def test_equivalence_passing(engine):
    passing_script = '''
def func_original(x):
    return x * 2

def func_optimized(x):
    return x + x

if func_original(5) == func_optimized(5):
    print("EQUIVALENCE_PASSED")
else:
    print("EQUIVALENCE_FAILED")
'''
    engine.client.aio.models.generate_content.return_value = MagicMock(text=f"```python\n{passing_script}\n```")

    original = "def compute(x):\n    return x * 2"
    optimized = "def compute(x):\n    return x + x"
    
    is_equiv = await engine._verify_equivalence(original, optimized)
    assert is_equiv is True

@pytest.mark.asyncio
async def test_equivalence_failing(engine):
    failing_script = '''
def func_original(x):
    return x * 2

def func_optimized(x):
    return x * 3

if func_original(5) == func_optimized(5):
    print("EQUIVALENCE_PASSED")
else:
    print("EQUIVALENCE_FAILED")
'''
    engine.client.aio.models.generate_content.return_value = MagicMock(text=f"```python\n{failing_script}\n```")

    original = "def compute(x):\n    return x * 2"
    optimized = "def compute(x):\n    return x * 3"
    
    is_equiv = await engine._verify_equivalence(original, optimized)
    assert is_equiv is False

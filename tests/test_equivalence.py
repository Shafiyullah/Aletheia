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
'''
    engine.client.aio.models.generate_content.return_value = MagicMock(text=f"```python\n{passing_script}\n```")

    original = "def compute(x):\n    return x * 2"
    optimized = "def compute(x):\n    return x + x"
    
    # Mock subprocess.run to simulate a successful CrossHair match
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            stdout="No differences found", 
            stderr="", 
            returncode=0
        )
        is_equiv = await engine._verify_equivalence(original, optimized)
        assert is_equiv is True

@pytest.mark.asyncio
async def test_equivalence_failing(engine):
    failing_script = '''
def func_original(x):
    return x * 2

def func_optimized(x):
    return x * 3
'''
    engine.client.aio.models.generate_content.return_value = MagicMock(text=f"```python\n{failing_script}\n```")

    original = "def compute(x):\n    return x * 2"
    optimized = "def compute(x):\n    return x * 3"
    
    # Mock subprocess.run to simulate a CrossHair detection of difference
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            stdout="different", 
            stderr="", 
            returncode=1
        )
        is_equiv = await engine._verify_equivalence(original, optimized)
        assert is_equiv is False

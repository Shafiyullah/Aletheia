import pytest
from core.safety import static_analysis_check, run_in_sandbox, SecurityViolationException, validate_imports

def test_static_analysis_dangerous_imports():
    bad_code = "import os\nos.system('ls')"
    with pytest.raises(SecurityViolationException) as excinfo:
        static_analysis_check(bad_code)
    assert "Banned import: os" in str(excinfo.value)

def test_static_analysis_safe():
    safe_code = "import numpy as np\nx = np.array([1, 2, 3])"
    # Should not raise
    static_analysis_check(safe_code)

def test_run_in_sandbox_safe():
    # Note: run_in_sandbox executes code. 
    # Ensure environment has numpy if needed, or use simple code.
    code = "print('hello world')"
    # run_in_sandbox returns captured stdout
    result = run_in_sandbox(code)
    assert "hello world" in result

def test_run_in_sandbox_violation():
    code = "import os"
    with pytest.raises(SecurityViolationException):
        run_in_sandbox(code)



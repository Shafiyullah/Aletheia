"""
Tests for the Shannon Taint Analysis Engine.

These tests validate that the taint propagation is REAL:
  - Sources are correctly identified.
  - Taint propagates through variable assignments.
  - Sanitizers break the taint chain.
  - Sinks receiving tainted data are flagged.
  - Clean code (hardcoded values) is NOT flagged.
"""

import pytest
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.shannon import analyze_taint, scan_code_for_sinks


class TestTaintSources:
    """Test that taint sources are correctly identified."""

    def test_input_is_tainted(self):
        """input() is a classic source of untrusted data."""
        code = "x = input('Enter: ')\neval(x)"
        result = analyze_taint(code)
        assert result["is_vulnerable"] is True
        assert result["vulnerability_count"] >= 1
        assert result["vulnerabilities"][0]["source_type"] == "user_input"
        assert result["vulnerabilities"][0]["sink"] == "eval"

    def test_os_environ_is_tainted(self):
        """os.environ.get() introduces environment variable data."""
        code = "import os\ncmd = os.environ.get('CMD')\nos.system(cmd)"
        result = analyze_taint(code)
        assert result["is_vulnerable"] is True
        assert any(v["source_type"] == "environment_variable" for v in result["vulnerabilities"])

    def test_function_params_are_tainted(self):
        """Function parameters are untrusted by default (callers control them)."""
        code = "def process(user_data):\n    eval(user_data)"
        result = analyze_taint(code)
        assert result["is_vulnerable"] is True
        assert result["vulnerabilities"][0]["source_type"] == "function_parameter"


class TestTaintPropagation:
    """Test that taint flows through assignments correctly."""

    def test_direct_assignment_propagates(self):
        """x = input(); y = x; eval(y) — taint must flow x → y → eval."""
        code = "x = input()\ny = x\neval(y)"
        result = analyze_taint(code)
        assert result["is_vulnerable"] is True
        assert result["vulnerabilities"][0]["tainted_variable"] == "y"

    def test_string_concat_propagates(self):
        """cmd = 'ls ' + user_input — taint propagates through concatenation."""
        code = "user_input = input()\ncmd = 'ls ' + user_input\nos.system(cmd)"
        result = analyze_taint(code)
        assert result["is_vulnerable"] is True

    def test_multi_hop_propagation(self):
        """a = input(); b = a; c = b; eval(c) — 3-hop chain."""
        code = "a = input()\nb = a\nc = b\neval(c)"
        result = analyze_taint(code)
        assert result["is_vulnerable"] is True
        chain = result["vulnerabilities"][0]["propagation_chain"]
        assert len(chain) >= 3  # source + 2 propagations + sink


class TestSanitizers:
    """Test that sanitizer functions break the taint chain."""

    def test_int_cast_sanitizes(self):
        """x = int(input()) — int() is a sanitizer, eval(x) should be safe."""
        code = "x = int(input())\neval(x)"
        result = analyze_taint(code)
        # int() breaks the taint chain, BUT eval still shows as a sink
        # The key is: x should no longer be tainted after int()
        tainted_names = [tv["name"] for tv in result["tainted_variables"]]
        assert "x" not in tainted_names


class TestCleanCode:
    """Test that hardcoded/safe code is NOT flagged."""

    def test_hardcoded_eval_is_safe(self):
        """eval('1+1') with a hardcoded string has no tainted variable reaching the sink."""
        code = "result = eval('1 + 1')"
        result = analyze_taint(code)
        assert result["is_vulnerable"] is False

    def test_no_sources_no_vulns(self):
        """Code with sinks but no sources should not be vulnerable."""
        code = "import os\nos.system('ls -la')"
        result = analyze_taint(code)
        assert result["is_vulnerable"] is False

    def test_pure_math_is_clean(self):
        """Pure computational code should have zero findings."""
        code = "import math\nx = math.sqrt(144)\nprint(x)"
        result = analyze_taint(code)
        assert result["is_vulnerable"] is False
        assert result["vulnerability_count"] == 0


class TestSinkDetection:
    """Test that various sink types are correctly identified."""

    def test_subprocess_sink(self):
        code = "import subprocess\ncmd = input()\nsubprocess.run(cmd, shell=True)"
        result = analyze_taint(code)
        assert result["is_vulnerable"] is True
        assert result["vulnerabilities"][0]["sink_type"] == "command_injection"

    def test_sql_injection_sink(self):
        code = "name = input()\ncursor.execute('SELECT * FROM users WHERE name=' + name)"
        result = analyze_taint(code)
        assert result["is_vulnerable"] is True
        assert result["vulnerabilities"][0]["sink_type"] == "sql_injection"


class TestLegacyAPI:
    """Test backward compatibility with old scan_code_for_sinks API."""

    def test_returns_list_of_dicts(self):
        code = "x = input()\neval(x)"
        result = scan_code_for_sinks(code)
        assert isinstance(result, list)
        assert len(result) >= 1
        assert "sink" in result[0]
        assert "lineno" in result[0]

    def test_syntax_error_returns_empty(self):
        code = "def broken(:"
        result = scan_code_for_sinks(code)
        assert result == []

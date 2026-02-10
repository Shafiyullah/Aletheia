import re
import io
import ast
import contextlib
import os
import json
from typing import Tuple, Optional
from google import genai
from core.config import MODEL_FAST

ALLOWED_LIBRARIES = {'numpy', 'pandas', 'jax', 'math', 'datetime', 'random', 'json', 're', 'collections', 'itertools', 'functools'}

class SecurityViolationException(Exception):
    """Raised when code violates security policies."""
    pass

class SecurityVisitor(ast.NodeVisitor):
    def __init__(self):
        self.violations = []

    def visit_Import(self, node):
        for alias in node.names:
            if alias.name in ['os', 'sys', 'subprocess', 'shutil', 'pickle']:
                self.violations.append(f"Banned import: {alias.name}")
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if node.module in ['os', 'sys', 'subprocess', 'shutil', 'pickle']:
            self.violations.append(f"Banned import from: {node.module}")
        self.generic_visit(node)

    def visit_Call(self, node):
        if isinstance(node.func, ast.Name):
            if node.func.id in ['exec', 'eval', 'open', 'globals', 'locals', '__import__']:
                self.violations.append(f"Banned function call: {node.func.id}")
        self.generic_visit(node)

    def visit_Attribute(self, node):
        if node.attr in ['__import__', '__subclasses__']:
            self.violations.append(f"Banned attribute access: {node.attr}")
        self.generic_visit(node)

def static_analysis_check(code_str: str) -> None:
    """
    Parses code into AST and checks for banned patterns.
    Raises SecurityViolationException if unsafe.
    """
    try:
        tree = ast.parse(code_str)
    except SyntaxError as e:
        raise SecurityViolationException(f"Syntax Error in code: {e}")

    visitor = SecurityVisitor()
    visitor.visit(tree)

    if visitor.violations:
        raise SecurityViolationException(f"Security Violations Found: {', '.join(visitor.violations)}")

def validate_imports(code_str: str) -> Tuple[bool, Optional[str]]:
    """
    Checks if all imported modules are in the ALLOWED_LIBRARIES whitelist.
    Returns: (is_valid, error_message_json)
    """
    try:
        tree = ast.parse(code_str)
    except SyntaxError:
        return False, json.dumps({
            "status": "dependency_error",
            "missing_lib": "syntax_error",
            "message": "Syntax Error: Unable to parse code for import validation."
        })

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                # Get the top-level package name (e.g., 'sklearn.metrics' -> 'sklearn')
                top_level_pkg = alias.name.split('.')[0]
                if top_level_pkg not in ALLOWED_LIBRARIES:
                    return False, json.dumps({
                        "status": "dependency_error",
                        "missing_lib": top_level_pkg,
                        "message": f"Library '{top_level_pkg}' is not available in the Demo Environment."
                    })
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                top_level_pkg = node.module.split('.')[0]
                if top_level_pkg not in ALLOWED_LIBRARIES:
                    return False, json.dumps({
                        "status": "dependency_error",
                        "missing_lib": top_level_pkg,
                        "message": f"Library '{top_level_pkg}' is not available in the Demo Environment."
                    })
    
    return True, None

def run_in_sandbox(code_str: str, global_vars: Optional[dict] = None) -> str:
    """
    Executes code in a restricted environment and captures output.
    """
    # 0. Dependency Check - Whitelist
    is_valid_deps, dep_error = validate_imports(code_str)
    if not is_valid_deps:
        return dep_error

    # 1. Static Analysis (AST) - Strict Blocking
    static_analysis_check(code_str)

    # 2. AI Sentinel - Intent Analysis
    ai_security_check(code_str)

    if global_vars is None:
        global_vars = {}
    
    # Restrict builtins
    safe_builtins = __builtins__.copy()
    if isinstance(safe_builtins, dict):
        # Already a dict in some environments
        pass
    else:
        # Get from module if it's a module
        import builtins
        safe_builtins = builtins.__dict__.copy()

    # Blacklist dangerous builtins
    for b in ['open', 'eval', 'exec', '__import__', 'compile']:
        safe_builtins.pop(b, None)

    global_vars['__builtins__'] = safe_builtins

    output = io.StringIO()
    try:
        with contextlib.redirect_stdout(output):
            exec(code_str, global_vars)
    except Exception as e:
        return f"Execution Error: {str(e)}"
    
    return output.getvalue()

def ai_security_check(code_str: str) -> None:
    """
    Uses Gemini to scan for malicious intent.
    Raises SecurityViolationException if unsafe.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return # Skip if no key (fallback to regex only)
        
    client = genai.Client(api_key=api_key)
    
    prompt = f"""
    ### ROLE: AI Security Sentinel
    ### TASK: Analyze this Python code for malicious intent (reverse shells, file deletion, env exfiltration, infinite loops).
    
    ### CODE:
    ```python
    {code_str}
    ```
    
    ### OUTPUT:
    Return ONLY 'SAFE' or 'BLOCK'. Do not explain.
    """
    
    try:
        # Synchronous call for safety check (blocking)
        response = client.models.generate_content(
            model=MODEL_FAST,
            contents=prompt
        )
        result = response.text.strip().upper()
        
        if "BLOCK" in result:
             raise SecurityViolationException("AI Sentinel detected malicious intent.")
             
    except Exception as e:
        if isinstance(e, SecurityViolationException):
            raise e
        # If API fails, default to safe (allow regex to catch obvious stuff)
        pass

async def ai_security_check_async(code_str: str) -> None:
    """
    Async version of ai_security_check for parallel execution.
    Uses Gemini to scan for malicious intent.
    Raises SecurityViolationException if unsafe.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return # Skip if no key (fallback to regex only)
        
    client = genai.Client(api_key=api_key)
    
    prompt = f"""
    ### ROLE: AI Security Sentinel
    ### TASK: Analyze this Python code for malicious intent (reverse shells, file deletion, env exfiltration, infinite loops).
    
    ### CODE:
    ```python
    {code_str}
    ```
    
    ### OUTPUT:
    Return ONLY 'SAFE' or 'BLOCK'. Do not explain.
    """
    
    try:
        # Async call for non-blocking execution
        response = await client.aio.models.generate_content(
            model=MODEL_FAST,
            contents=prompt
        )
        result = response.text.strip().upper()
        
        if "BLOCK" in result:
             raise SecurityViolationException("AI Sentinel detected malicious intent.")
             
    except Exception as e:
        if isinstance(e, SecurityViolationException):
            raise e
        # If API fails, default to safe (allow regex to catch obvious stuff)
        pass


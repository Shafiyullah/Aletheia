import re
import io
import ast
import contextlib
import os
import json
import math
import logging
from typing import Tuple, Optional, List
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
                        "message": f"Library '{top_level_pkg}' execution blocked by security sandbox policy."
                    })
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                top_level_pkg = node.module.split('.')[0]
                if top_level_pkg not in ALLOWED_LIBRARIES:
                    return False, json.dumps({
                        "status": "dependency_error",
                        "missing_lib": top_level_pkg,
                        "message": f"Library '{top_level_pkg}' execution blocked by security sandbox policy."
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

# --- Deterministic Output Firewall (Zero API calls) ---

_INJECTION_PATTERNS: List[re.Pattern] = [
    re.compile(r'ignore\s+(all\s+)?previous\s+instructions', re.IGNORECASE),
    re.compile(r'ignore\s+(all\s+)?above\s+instructions', re.IGNORECASE),
    re.compile(r'you\s+are\s+now\s+(a|an|in)\s+', re.IGNORECASE),
    re.compile(r'forget\s+(everything|all|your)\s+(you|above|previous)', re.IGNORECASE),
    re.compile(r'system\s*prompt\s*:', re.IGNORECASE),
    re.compile(r'\bDAN\s+mode\b', re.IGNORECASE),
    re.compile(r'jailbreak', re.IGNORECASE),
    re.compile(r'act\s+as\s+if\s+you\s+have\s+no\s+(restrictions|rules|guidelines)', re.IGNORECASE),
    re.compile(r'reveal\s+(the|your)\s+(secret|system|hidden|internal)', re.IGNORECASE),
    re.compile(r'\[\s*SYSTEM\s*\]', re.IGNORECASE),
]

_SECRET_PATTERNS: List[re.Pattern] = [
    re.compile(r'(?:api[_-]?key|apikey|secret[_-]?key|access[_-]?token)\s*[=:]\s*["\']?[A-Za-z0-9_\-]{20,}', re.IGNORECASE),
    re.compile(r'AIza[0-9A-Za-z_\-]{35}'),
    re.compile(r'sk-[A-Za-z0-9]{40,}'),
    re.compile(r'ghp_[A-Za-z0-9]{36,}'),
    re.compile(r'-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----'),
    re.compile(r'password\s*[=:]\s*["\'][^"\']+(["\']+)', re.IGNORECASE),
]


def _shannon_entropy(text: str) -> float:
    """Shannon entropy of a string. High entropy = possibly encoded/encrypted data."""
    if not text:
        return 0.0
    freq = {}
    for c in text:
        freq[c] = freq.get(c, 0) + 1
    length = len(text)
    return -sum((count / length) * math.log2(count / length) for count in freq.values())


def validate_llm_output(output_text: str) -> None:
    """
    Deterministic Output Firewall. Zero API calls.
    
    Checks:
      1. Prompt Injection Detection — regex scan for known jailbreak patterns.
      2. Secret Leak Detection — regex + Shannon entropy for API keys, passwords, 
         and encoded payloads.
      3. Code Safety Scan — if the output contains Python code blocks, run them 
         through the existing AST-based static_analysis_check.
      4. Structural Validation — if the output is JSON, validate and scan 
         embedded code fields.
    
    Raises SecurityViolationException if any check fails.
    """
    violations = []

    # --- Check 1: Prompt Injection Detection ---
    for pattern in _INJECTION_PATTERNS:
        match = pattern.search(output_text)
        if match:
            violations.append(f"Prompt injection artifact detected: '{match.group()}'")

    # --- Check 2: Secret/Credential Leak Detection ---
    for pattern in _SECRET_PATTERNS:
        match = pattern.search(output_text)
        if match:
            redacted = match.group()[:10] + "...REDACTED"
            violations.append(f"Potential credential leak detected: '{redacted}'")

    # Entropy check for encoded payloads
    for line in output_text.split('\n'):
        stripped = line.strip()
        if len(stripped) > 40:
            entropy = _shannon_entropy(stripped)
            if entropy > 5.5:  # English ~3.5-4.5; base64/encoded ~5.5+
                violations.append(
                    f"High-entropy line detected (entropy={entropy:.2f}), "
                    f"possible encoded payload: '{stripped[:30]}...'"
                )

    # --- Check 3: Code Safety Scan ---
    code_blocks = re.findall(r'```python\s*\n(.*?)```', output_text, re.DOTALL)
    if not code_blocks:
        code_blocks = re.findall(r'```\s*\n(.*?)```', output_text, re.DOTALL)
    for code_block in code_blocks:
        try:
            static_analysis_check(code_block)
        except SecurityViolationException as e:
            violations.append(f"Embedded code failed AST safety scan: {str(e)}")

    # --- Check 4: Structural Validation ---
    trimmed = output_text.strip()
    if trimmed.startswith('{') or trimmed.startswith('['):
        try:
            parsed = json.loads(trimmed)
            if isinstance(parsed, dict) and "code" in parsed:
                code_content = parsed["code"]
                if isinstance(code_content, str) and code_content.strip():
                    try:
                        static_analysis_check(code_content)
                    except SecurityViolationException as e:
                        violations.append(f"Code in JSON payload failed AST safety scan: {str(e)}")
        except json.JSONDecodeError:
            logging.warning("Output resembles JSON but failed to parse.")

    # --- Verdict ---
    if violations:
        violation_summary = "; ".join(violations)
        logging.error(f"[OUTPUT FIREWALL] BLOCKED: {violation_summary}")
        raise SecurityViolationException(
            f"[FIREWALL BLOCKED] {len(violations)} violation(s) detected: {violation_summary}"
        )
    else:
        logging.info("[OUTPUT FIREWALL] Output passed all checks.")


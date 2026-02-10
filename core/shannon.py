
import ast
import os
import json
import logging
from typing import List, Dict, Any, Optional, Tuple
from google import genai
from core.config import MODEL_SMART, MODEL_FAST

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [%(levelname)s] - %(name)s - %(message)s')

DANGEROUS_SINKS = ['eval', 'exec', 'os.system', 'subprocess.run', 'subprocess.call', 'sqlite3.execute']

class ShannonTracer(ast.NodeVisitor):
    """
    AST Walker that identifies calls to dangerous functions (sinks).
    """
    def __init__(self, source_code: str):
        self.source_code = source_code
        self.sinks_found = []

    def visit_Call(self, node):
        func_name = self._get_func_name(node.func)
        if func_name and any(sink in func_name for sink in DANGEROUS_SINKS):
            # Found a potential vulnerability
            args_str = self._extract_args(node)
            self.sinks_found.append({
                "sink": func_name,
                "args": args_str,
                "lineno": node.lineno,
                "col_offset": node.col_offset
            })
        self.generic_visit(node)

    def _get_func_name(self, node) -> Optional[str]:
        """Resolves function names like 'os.system' or 'eval'."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            value_name = self._get_func_name(node.value)
            if value_name:
                return f"{value_name}.{node.attr}"
            return node.attr
        return None

    def _extract_args(self, node) -> str:
        """Extracts the source code of the arguments passed to the function."""
        if not node.args:
            return "()"
        
        # In a real implementation with Python < 3.8, we'd need a complex slicer.
        # Python 3.8+ has unparse, but we want the exact string if possible.
        # For this hackathon, we'll try ast.unparse (Python 3.9+) or fallback to string representation.
        try:
            return ast.unparse(node)
        except AttributeError:
             return str([ast.dump(arg) for arg in node.args])

def scan_code_for_sinks(code_str: str) -> List[Dict[str, Any]]:
    """
    Parses code and finds all dangerous sinks.
    """
    try:
        tree = ast.parse(code_str)
    except SyntaxError:
        return [] # Syntax error, can't analysis
        
    tracer = ShannonTracer(code_str)
    tracer.visit(tree)
    return tracer.sinks_found

async def verify_vulnerability(code_snippet: str, sink_name: str, args: str) -> Tuple[bool, Optional[str]]:
    """
    Uses Gemini to verify if a sink is reachable from user input (Taint Analysis).
    Returns: (is_vulnerable, exploit_payload)
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return False, "Missing API Key"
        
    client = genai.Client(api_key=api_key)
    
    prompt = f"""
    ### ROLE: Senior Security Engineer (Shannon Engine)
    ### TASK: Taint Analysis & Vulnerability Verification
    
    Review this Python code.
    A dangerous function `{sink_name}` is called with arguments `{args}`.
    
    TRACE the data flow. Does the data come from a user input, network request, or an insecure/unsanitized source?
    
    ### CODE:
    ```python
    {code_snippet}
    ```
    
    ### OUTPUT VALIDATION:
    1. If YES (Vulnerable): Return a JSON object with `{{ "vulnerable": true, "exploit": "example_payload_to_trigger_it" }}`.
    2. If NO (Safe/Hardcoded): Return `{{ "vulnerable": false }}`.
    
    Return ONLY VALID JSON.
    """
    
    try:
        response = await client.aio.models.generate_content(
            model=MODEL_SMART,
            contents=prompt
        )
        
        text = response.text.strip()
        if text.startswith("```json"):
            text = text[7:-3]
            
        data = json.loads(text)
        return data.get("vulnerable", False), data.get("exploit")
        
    except Exception as e:
        logging.error(f"Shannon Verification Error: {e}")
        return False, None

async def patch_vulnerability(code_snippet: str, exploit_payload: str) -> str:
    """
    Uses Gemini to patch the code against the identified exploit.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return code_snippet
        
    client = genai.Client(api_key=api_key)
    
    prompt = f"""
    ### ROLE: Security Patcher
    ### TASK: Fix this vulnerability.
    
    The code below has a security vulnerability exploitable by: `{exploit_payload}`.
    
    ### CODE:
    ```python
    {code_snippet}
    ```
    
    ### INSTRUCTIONS:
    1. Replace the dangerous sink with a secure alternative (e.g., `subprocess.run` with `shell=False` and list args, or `sql` parameters).
    2. Add input validation if necessary.
    3. Return ONLY the fully fixed Python code. No markdown formatting.
    """
    
    try:
        response = await client.aio.models.generate_content(
            model=MODEL_SMART,
            contents=prompt
        )
        return response.text.replace("```python", "").replace("```", "").strip()
        
    except Exception as e:
        logging.error(f"Shannon Patch Error: {e}")
        return code_snippet

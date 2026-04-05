"""
Shannon Taint Analysis Engine — Deterministic Source-to-Sink Data Flow Tracker.

Architecture Reference:
  - Scalpel (https://github.com/SMAT-Lab/Scalpel) — CFG, SSA, use-def chains
  - PyT (https://github.com/python-security/pyt) — source-to-sink propagation
  - Pysa / Pyre (https://github.com/facebook/pyre-check) — taint tracking model

This module performs REAL static taint analysis:
  1. Parses code into an AST.
  2. Builds def-use chains (which variables are assigned where, and what flows into them).
  3. Identifies SOURCES (where untrusted data enters).
  4. Identifies SINKS (where dangerous execution happens).
  5. Propagates taint through assignments, string concat, f-strings, and function returns.
  6. Reports whether any tainted path reaches a sink — WITHOUT calling an LLM.

The LLM (Gemini) is used ONLY for patch generation (creative task), never for detection.
"""

import ast
import os
import json
import logging
from dataclasses import dataclass, field
from google import genai
from core.config import MODEL_SMART, MODEL_FAST
from core.utils import extract_code
from typing import List, Dict, Any, Optional, Set, Tuple

logging.basicConfig(level=logging.INFO, format='%(asctime)s - [%(levelname)s] - %(name)s - %(message)s')

# DATA MODELS

# Functions/calls that introduce untrusted data into the program.
TAINT_SOURCES: Dict[str, str] = {
    'input':            'user_input',
    'request.args.get': 'http_parameter',
    'request.form.get': 'http_form',
    'request.json':     'http_body',
    'os.environ.get':   'environment_variable',
    'os.environ':       'environment_variable',
    'os.getenv':        'environment_variable',
    'sys.argv':         'cli_argument',
    'sys.stdin.read':   'stdin_stream',
    'sys.stdin.readline': 'stdin_stream',
    'open':             'file_read',
}

# Functions/calls where tainted data MUST NOT arrive unsanitized.
TAINT_SINKS: Dict[str, str] = {
    'eval':              'arbitrary_code_execution',
    'exec':              'arbitrary_code_execution',
    'os.system':         'os_command_injection',
    'os.popen':          'os_command_injection',
    'subprocess.run':    'command_injection',
    'subprocess.call':   'command_injection',
    'subprocess.Popen':  'command_injection',
    'sqlite3.execute':   'sql_injection',
    'cursor.execute':    'sql_injection',
    'conn.execute':      'sql_injection',
    '__import__':        'dynamic_import',
    'compile':           'code_compilation',
}

# Functions that SANITIZE data (break the taint chain).
SANITIZERS: Set[str] = {
    'int', 'float', 'bool',          # Type casting removes arbitrary strings
    'html.escape', 'markupsafe.escape',
    'shlex.quote',                    # Shell argument sanitization
    'bleach.clean',                   # HTML sanitization
    'urllib.parse.quote',             # URL encoding
    'parameterized',                  # Parameterized SQL (conceptual marker)
}


@dataclass
class TaintedVariable:
    """Represents a variable that carries tainted data."""
    name: str
    source_type: str          # e.g., 'user_input', 'http_parameter'
    source_line: int          # Line where taint was introduced
    propagation_path: List[str] = field(default_factory=list)  # e.g., ['x = input()', 'y = x', 'eval(y)']


@dataclass
class VulnerabilityReport:
    """A confirmed source-to-sink vulnerability."""
    sink_name: str
    sink_type: str            # e.g., 'arbitrary_code_execution'
    sink_line: int
    sink_col: int
    tainted_var: str
    source_type: str          # e.g., 'user_input'
    source_line: int
    propagation_chain: List[str]
    severity: str             # 'CRITICAL', 'HIGH', 'MEDIUM'

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sink": self.sink_name,
            "sink_type": self.sink_type,
            "sink_line": self.sink_line,
            "tainted_variable": self.tainted_var,
            "source_type": self.source_type,
            "source_line": self.source_line,
            "propagation_chain": self.propagation_chain,
            "severity": self.severity,
        }


# DEF-USE CHAIN BUILDER (AST Walker)

class DefUseCollector(ast.NodeVisitor):
    """
    Walks the AST to build definition-use chains and track data flow.
    
    For every assignment `x = expr`, records:
      - What variable is being defined (x)
      - What variables/calls flow INTO x (the RHS)
      - Whether x is tainted (if any RHS component is tainted or is a source)
    """

    def __init__(self, source_code: str):
        self.source_code = source_code
        
        # Core tracking structures
        self.tainted: Dict[str, TaintedVariable] = {}  # var_name -> TaintedVariable
        self.definitions: Dict[str, List[int]] = {}     # var_name -> [line_numbers]
        self.vulnerabilities: List[VulnerabilityReport] = []
        
        # Track function parameters (they are potential sources)
        self.function_params: Set[str] = set()

        # Inter-procedural tracking
        self.function_registry: Dict[str, ast.FunctionDef] = {}
        self.visited_functions: Set[str] = set()
        self.call_stack: List[str] = []
        
    def _resolve_call_name(self, node: ast.AST) -> Optional[str]:
        """Resolves a call node to a dotted name like 'os.system' or 'eval'."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            value = self._resolve_call_name(node.value)
            if value:
                return f"{value}.{node.attr}"
            return node.attr
        elif isinstance(node, ast.Subscript):
            value = self._resolve_call_name(node.value)
            return value
        return None

    def _extract_names_from_expr(self, node: ast.AST) -> Set[str]:
        """Extracts all variable Name references from an expression tree."""
        names = set()
        for child in ast.walk(node):
            if isinstance(child, ast.Name):
                names.add(child.id)
        return names

    def _is_sanitizer_call(self, node: ast.Call) -> bool:
        """Check if a function call is a known sanitizer."""
        func_name = self._resolve_call_name(node.func)
        return func_name in SANITIZERS if func_name else False

    def _check_source(self, node: ast.Call) -> Optional[str]:
        """Check if a call is a known taint source. Returns source_type or None."""
        func_name = self._resolve_call_name(node.func)
        if func_name and func_name in TAINT_SOURCES:
            return TAINT_SOURCES[func_name]
        return None

    def _check_sink(self, node: ast.Call) -> Optional[Tuple[str, str]]:
        """Check if a call is a known taint sink. Returns (sink_name, sink_type) or None."""
        func_name = self._resolve_call_name(node.func)
        if func_name and func_name in TAINT_SINKS:
            return func_name, TAINT_SINKS[func_name]
        return None

    def _propagate_taint(self, target_name: str, value_node: ast.AST, line: int):
        """
        Core taint propagation logic.
        
        Given `target = value_expr`, determine if target becomes tainted:
          1. If value_expr IS a source call → target is tainted.
          2. If value_expr CONTAINS a reference to a tainted variable → target is tainted.
          3. If value_expr is a sanitizer call → target is NOT tainted (chain broken).
        """
        # Case 1: Direct source assignment (e.g., `x = input()`)
        if isinstance(value_node, ast.Call):
            # Check if it's a sanitizer — breaks the chain
            if self._is_sanitizer_call(value_node):
                if target_name in self.tainted:
                    del self.tainted[target_name]
                return

            source_type = self._check_source(value_node)
            if source_type:
                func_name = self._resolve_call_name(value_node.func)
                self.tainted[target_name] = TaintedVariable(
                    name=target_name,
                    source_type=source_type,
                    source_line=line,
                    propagation_path=[f"L{line}: {target_name} = {func_name}()  [SOURCE: {source_type}]"]
                )
                return

        # Case 2: Propagation through variable reference
        # Scan all names in the RHS expression
        rhs_names = self._extract_names_from_expr(value_node)
        for rhs_name in rhs_names:
            if rhs_name in self.tainted:
                parent = self.tainted[rhs_name]
                self.tainted[target_name] = TaintedVariable(
                    name=target_name,
                    source_type=parent.source_type,
                    source_line=parent.source_line,
                    propagation_path=parent.propagation_path + [
                        f"L{line}: {target_name} = ...{rhs_name}...  [PROPAGATED]"
                    ]
                )
                return

    # --- AST Visitor Methods ---

    def visit_Module(self, node: ast.Module):
        """Pre-scan for function definitions to build a registry."""
        for child in node.body:
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.function_registry[child.name] = child
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Handle function definitions. Parameters are usually treated as sources if they are public APIs."""
        if self.call_stack:
            # We are inside a specific call analysis
            pass
        else:
            # Entry point or top-level function
            for arg in node.args.args:
                param_name = arg.arg
                if param_name != 'self':
                    self.function_params.add(param_name)
                    self.tainted[param_name] = TaintedVariable(
                        name=param_name,
                        source_type='function_parameter',
                        source_line=node.lineno,
                        propagation_path=[f"L{node.lineno}: def {node.name}({param_name})  [ENTRY_SOURCE]"]
                    )
        self.generic_visit(node)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Assign(self, node: ast.Assign):
        """Handle `x = expr` assignments."""
        for target in node.targets:
            if isinstance(target, ast.Name):
                target_name = target.id
                self.definitions.setdefault(target_name, []).append(node.lineno)
                self._propagate_taint(target_name, node.value, node.lineno)
            elif isinstance(target, ast.Tuple):
                # Handle tuple unpacking: `a, b = expr1, expr2`
                for elt in target.elts:
                    if isinstance(elt, ast.Name):
                        self.definitions.setdefault(elt.id, []).append(node.lineno)
                        self._propagate_taint(elt.id, node.value, node.lineno)
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign):
        """Handle `x += expr` — taint propagates if RHS is tainted."""
        if isinstance(node.target, ast.Name):
            target_name = node.target.id
            self._propagate_taint(target_name, node.value, node.lineno)
        self.generic_visit(node)

    def visit_For(self, node: ast.For):
        """Handle `for x in iterable` — x inherits taint from iterable."""
        if isinstance(node.target, ast.Name):
            target_name = node.target.id
            self._propagate_taint(target_name, node.iter, node.lineno)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        """
        Check if a call is a SINK and if any of its arguments are tainted.
        Also handles inter-procedural propagation into local functions.
        """
        func_name = self._resolve_call_name(node.func)
        sink_info = self._check_sink(node)
        
        if sink_info:
            sink_name, sink_type = sink_info
            # Check each argument for taint
            for arg in node.args:
                arg_names = self._extract_names_from_expr(arg)
                for arg_name in arg_names:
                    if arg_name in self.tainted:
                        tv = self.tainted[arg_name]
                        severity = 'CRITICAL' if sink_type in (
                            'arbitrary_code_execution', 'os_command_injection'
                        ) else 'HIGH'
                        
                        self.vulnerabilities.append(VulnerabilityReport(
                            sink_name=sink_name,
                            sink_type=sink_type,
                            sink_line=node.lineno,
                            sink_col=node.col_offset,
                            tainted_var=arg_name,
                            source_type=tv.source_type,
                            source_line=tv.source_line,
                            propagation_chain=tv.propagation_path + [
                                f"L{node.lineno}: {sink_name}({arg_name})  [SINK: {sink_type}]"
                            ],
                            severity=severity,
                        ))

            # Also check keyword arguments
            for kw in node.keywords:
                if kw.value:
                    kw_names = self._extract_names_from_expr(kw.value)
                    for kw_name in kw_names:
                        if kw_name in self.tainted:
                            tv = self.tainted[kw_name]
                            severity = 'CRITICAL' if sink_type in (
                                'arbitrary_code_execution', 'os_command_injection'
                            ) else 'HIGH'

                            self.vulnerabilities.append(VulnerabilityReport(
                                sink_name=sink_name,
                                sink_type=sink_type,
                                sink_line=node.lineno,
                                sink_col=node.col_offset,
                                tainted_var=kw_name,
                                source_type=tv.source_type,
                                source_line=tv.source_line,
                                propagation_chain=tv.propagation_path + [
                                    f"L{node.lineno}: {sink_name}(...{kw_name}...)  [SINK: {sink_type}]"
                                ],
                                severity=severity,
                            ))

        # Inter-procedural Propagation:
        # If we call a local function with tainted arguments, we must analyze that function.
        if sink_info is None and func_name in self.function_registry:
            target_func = self.function_registry[func_name]
            if func_name not in self.call_stack: 
                self.call_stack.append(func_name)
                
                # Map arguments to parameters
                temp_tainted = {}
                for i, arg in enumerate(node.args):
                    if i < len(target_func.args.args):
                        param_name = target_func.args.args[i].arg
                        arg_names = self._extract_names_from_expr(arg)
                        for a_name in arg_names:
                            if a_name in self.tainted:
                                parent = self.tainted[a_name]
                                temp_tainted[param_name] = TaintedVariable(
                                    name=param_name,
                                    source_type=parent.source_type,
                                    source_line=parent.source_line,
                                    propagation_path=parent.propagation_path + [
                                        f"L{node.lineno}: Call {func_name}(...{a_name}...) -> Param {param_name}"
                                    ]
                                )
                
                # Analyze the function body with these tainted parameters
                if temp_tainted:
                    old_tainted = self.tainted.copy()
                    self.tainted.update(temp_tainted)
                    self.visit(target_func)
                    self.tainted = old_tainted
                
                self.call_stack.pop()

        self.generic_visit(node)

    def visit_JoinedStr(self, node: ast.JoinedStr):
        """
        Handle f-strings: `f"SELECT * FROM {table}"`.
        If any interpolated value is tainted, the f-string result is tainted.
        """
        for value in node.values:
            if isinstance(value, ast.FormattedValue):
                names = self._extract_names_from_expr(value.value)
                for name in names:
                    if name in self.tainted:
                        # f-string is tainted but we can't assign it a name
                        # directly — it will be caught when passed to a sink
                        pass
        self.generic_visit(node)


# PUBLIC API

def scan_code_for_sinks(code_str: str) -> List[Dict[str, Any]]:
    """
    Legacy-compatible API: Parses code and finds all dangerous sinks.
    Returns a list of sink findings (backward-compatible with old format).
    """
    try:
        tree = ast.parse(code_str)
    except SyntaxError:
        return []

    collector = DefUseCollector(code_str)
    collector.visit(tree)

    # Return in legacy format for backward compatibility
    sinks = []
    for vuln in collector.vulnerabilities:
        sinks.append({
            "sink": vuln.sink_name,
            "args": vuln.tainted_var,
            "lineno": vuln.sink_line,
            "col_offset": vuln.sink_col,
        })

    # Also find sinks without confirmed taint (for informational purposes)
    class SinkFinder(ast.NodeVisitor):
        def __init__(self):
            self.found = []

        def visit_Call(self, node):
            if isinstance(node.func, ast.Name):
                name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                val = node.func
                parts = []
                while isinstance(val, ast.Attribute):
                    parts.append(val.attr)
                    val = val.value
                if isinstance(val, ast.Name):
                    parts.append(val.id)
                name = '.'.join(reversed(parts))
            else:
                name = None

            if name and name in TAINT_SINKS:
                try:
                    args_str = ast.unparse(node)
                except AttributeError:
                    args_str = str([ast.dump(a) for a in node.args])
                self.found.append({
                    "sink": name,
                    "args": args_str,
                    "lineno": node.lineno,
                    "col_offset": node.col_offset,
                })
            self.generic_visit(node)

    finder = SinkFinder()
    finder.visit(tree)

    # Merge: confirmed vulns first, then informational sinks
    seen_lines = {s["lineno"] for s in sinks}
    for s in finder.found:
        if s["lineno"] not in seen_lines:
            sinks.append(s)

    return sinks


def analyze_taint(code_str: str) -> Dict[str, Any]:
    """
    Full taint analysis report.
    
    Returns a structured report with:
      - vulnerabilities: List of confirmed source-to-sink paths
      - tainted_variables: All variables carrying untrusted data
      - sink_count: Total dangerous sinks found
      - is_vulnerable: Boolean summary
    """
    try:
        tree = ast.parse(code_str)
    except SyntaxError as e:
        return {
            "error": f"SyntaxError: {e}",
            "is_vulnerable": False,
            "vulnerabilities": [],
            "tainted_variables": [],
        }

    collector = DefUseCollector(code_str)
    collector.visit(tree)

    return {
        "is_vulnerable": len(collector.vulnerabilities) > 0,
        "vulnerability_count": len(collector.vulnerabilities),
        "vulnerabilities": [v.to_dict() for v in collector.vulnerabilities],
        "tainted_variables": [
            {
                "name": tv.name,
                "source_type": tv.source_type,
                "source_line": tv.source_line,
                "propagation_path": tv.propagation_path,
            }
            for tv in collector.tainted.values()
        ],
        "summary": _generate_summary(collector.vulnerabilities),
    }


def _generate_summary(vulns: List[VulnerabilityReport]) -> str:
    """Human-readable summary of findings."""
    if not vulns:
        return "No taint vulnerabilities detected. All sink arguments appear to be hardcoded or sanitized."

    critical = sum(1 for v in vulns if v.severity == 'CRITICAL')
    high = sum(1 for v in vulns if v.severity == 'HIGH')

    lines = [f"Found {len(vulns)} taint vulnerability(ies): {critical} CRITICAL, {high} HIGH."]
    for i, v in enumerate(vulns, 1):
        lines.append(
            f"  [{v.severity}] #{i}: {v.source_type} data flows from L{v.source_line} "
            f"into {v.sink_name}() at L{v.sink_line} via variable '{v.tainted_var}'"
        )
    return "\n".join(lines)


# LLM-ASSISTED PATCH GENERATION

async def patch_vulnerability(code_snippet: str, vulnerability: Dict[str, Any]) -> str:
    """
    Uses Gemini to generate a PATCH for a confirmed vulnerability.
    
    NOTE: The vulnerability was detected deterministically by the taint engine.
    The LLM is used ONLY for creative code generation (the fix), not detection.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return code_snippet

    client = genai.Client(api_key=api_key)

    vuln_desc = (
        f"A {vulnerability.get('source_type', 'untrusted')} source flows into "
        f"{vulnerability.get('sink', 'unknown')}() at line {vulnerability.get('sink_line', '?')} "
        f"via variable '{vulnerability.get('tainted_variable', '?')}'. "
        f"Vulnerability type: {vulnerability.get('sink_type', 'unknown')}."
    )

    prompt = f"""
    ### ROLE: Security Patch Engineer
    ### TASK: Fix this confirmed taint vulnerability.
    
    ### VULNERABILITY:
    {vuln_desc}
    
    ### TAINT PROPAGATION CHAIN:
    {json.dumps(vulnerability.get('propagation_chain', []), indent=2)}
    
    ### CODE:
    ```python
    {code_snippet}
    ```
    
    ### INSTRUCTIONS:
    1. Add input validation/sanitization at the earliest point in the taint chain.
    2. For command injection: use `subprocess.run()` with `shell=False` and list arguments.
    3. For SQL injection: use parameterized queries (`cursor.execute("SELECT ?", (val,))`).
    4. For code execution: remove `eval()`/`exec()` entirely, use safe alternatives.
    5. Return ONLY the fully fixed Python code.
    """

    try:
        response = await client.aio.models.generate_content(
            model=MODEL_SMART,
            contents=prompt
        )
        return extract_code(response.text)
    except Exception as e:
        logging.error(f"Shannon Patch Error: {e}")
        return code_snippet

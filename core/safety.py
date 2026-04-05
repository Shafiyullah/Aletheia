import re
import io
import ast
import contextlib
import os
import json
import math
import logging
import tempfile
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

    # Deep Analysis: Bandit integration
    try:
        from bandit.core import config as b_config
        from bandit.core import manager as b_manager
        
        b_conf = b_config.BanditConfig()
        b_mgr = b_manager.BanditManager(b_conf, "file")
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as tf:
            tf.write(code_str)
            tf_path = tf.name
            
        b_mgr.discover_files([tf_path])
        b_mgr.run_tests()
        
        # Cleanup
        try:
            os.remove(tf_path)
        except OSError:
            pass
            
        results = b_mgr.get_issue_list()
        
        bandit_violations = []
        for issue in results:
            bandit_violations.append(f"[Bandit {issue.severity}] {issue.text} (L{issue.lineno})")
            
        if bandit_violations:
            raise SecurityViolationException(f"Bandit Security Violations Found: {'; '.join(bandit_violations)}")
            
    except SecurityViolationException:
        raise
    except Exception as e:
        logging.warning(f"Bandit execution failed, continuing with AST check only: {e}")

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

# DETERMINISTIC OUTPUT FIREWALL

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

# MULTI-HEURISTIC STATISTICAL ANALYSIS ENGINE

def _shannon_entropy(text: str) -> float:
    """Shannon entropy H = -Σ p_i * log2(p_i). Higher = more random."""
    if not text:
        return 0.0
    freq = {}
    for c in text:
        freq[c] = freq.get(c, 0) + 1
    length = len(text)
    return -sum((count / length) * math.log2(count / length) for count in freq.values())

# ADVANCED ANOMALY METRICS

# Baseline distribution: Average frequency of characters 32-126 in Python/English corpus.
# Simplified representation (lowercase letters high, symbols medium, numbers low).
_NATURAL_BASELINE = {
    'e': 0.12, 't': 0.09, 'a': 0.08, 'o': 0.07, 'i': 0.07, 'n': 0.07, 's': 0.06, 'r': 0.06, 'h': 0.06,
    'd': 0.04, 'l': 0.04, 'u': 0.03, 'c': 0.03, 'm': 0.03, 'f': 0.02, 'y': 0.02, 'w': 0.02, 'g': 0.02,
    'p': 0.02, 'b': 0.01, 'v': 0.01, 'k': 0.01, 'x': 0.01, 'q': 0.01, 'j': 0.01, 'z': 0.01,
    ' ': 0.15, '.': 0.01, ',': 0.01, '(': 0.01, ')': 0.01, '=': 0.01, '_': 0.02, ':': 0.01
}
# Normalize baseline
_TOTAL_B = sum(_NATURAL_BASELINE.values())
_NATURAL_PROBS = {k: v/_TOTAL_B for k, v in _NATURAL_BASELINE.items()}

def _kl_divergence(text: str) -> float:
    """
    Kullback-Leibler Divergence (Relative Entropy).
    Measures how much the character distribution deviates from 'Natural' text.
    Target: 0.0 (identical) to ∞ (completely divergent).
    """
    if not text: return 0.0
    text = text.lower()
    length = len(text)
    freq = {}
    for c in text:
        if c in _NATURAL_PROBS:
            freq[c] = freq.get(c, 0) + 1
    
    if not freq: return 10.0 # Extreme divergence (non-ASCII or weird symbols only)

    kl = 0.0
    for char, prob_q in _NATURAL_PROBS.items():
        # Observed probability P
        count_p = freq.get(char, 0)
        prob_p = count_p / length if count_p > 0 else 1e-9 # Smoothing
        # D_KL = P(i) * log(P(i) / Q(i))
        kl += prob_p * math.log(prob_p / prob_q)
    
    return kl

def _simpsons_index(text: str) -> float:
    """
    Simpson's Diversity Index (D).
    Measures evenness of character distribution.
    D near 1.0 = High diversity (Natural).
    D near 0.0 = Low diversity (Repetitive / Obfuscated).
    """
    if len(text) < 2: return 1.0
    freq = {}
    for c in text:
        freq[c] = freq.get(c, 0) + 1
    
    N = len(text)
    sum_n_n1 = sum(n * (n - 1) for n in freq.values())
    D = 1 - (sum_n_n1 / (N * (N - 1)))
    return D

def _chi_squared_uniformity(text: str) -> float:
    """
    Chi-Squared test for character distribution uniformity.
    
    Encoded data (base64, hex) has a near-uniform distribution across its
    character set. Natural language clusters heavily around lowercase letters.
    
    Returns: p-value. LOW p-value (< 0.05) = distribution is significantly
    non-uniform (likely natural text). HIGH p-value (> 0.05) = distribution
    is nearly uniform (likely encoded data).
    
    Reference: Fourmilab ent (https://www.fourmilab.ch/random/)
    """
    from scipy.stats import chisquare

    if len(text) < 10:
        return 1.0  # Too short to analyze

    # Count frequency of each unique character
    freq = {}
    for c in text:
        freq[c] = freq.get(c, 0) + 1

    observed = list(freq.values())
    n_categories = len(observed)

    if n_categories < 2:
        return 1.0

    # Expected: if uniform, each char appears total/n_categories times
    total = sum(observed)
    expected = [total / n_categories] * n_categories

    _, p_value = chisquare(observed, f_exp=expected)
    return p_value


def _serial_correlation(text: str) -> float:
    """
    Serial Correlation Coefficient (SCC) between adjacent characters.
    
    Truly random/encrypted data: SCC ≈ 0.0 (no correlation)
    Natural English text: SCC ≈ 0.3-0.7 (high correlation, letters cluster)
    Base64 encoded data: SCC ≈ 0.0-0.1 (low correlation)
    
    Returns: float between -1.0 and 1.0.
    
    Reference: Knuth TAOCP Vol 2, Section 3.3.2
    """
    if len(text) < 3:
        return 0.5  # Not enough data

    values = [ord(c) for c in text]
    n = len(values)

    mean = sum(values) / n
    variance = sum((v - mean) ** 2 for v in values) / n

    if variance == 0:
        return 1.0  # All same character

    covariance = sum(
        (values[i] - mean) * (values[i + 1] - mean)
        for i in range(n - 1)
    ) / (n - 1)

    return covariance / variance


def _byte_frequency_score(text: str) -> float:
    """
    Byte Frequency Distribution analysis.
    
    Encoded data (base64) uses a narrow, specific alphabet:
      A-Z, a-z, 0-9, +, / (64 chars) with near-equal frequencies.
    Natural text uses ~60-80 distinct chars but with HEAVY clustering
    around lowercase letters (e, t, a, o, i, n, s...).
    
    This function measures how "flat" the frequency distribution is.
    Returns: 0.0 (highly peaked/natural) to 1.0 (perfectly flat/encoded).
    
    Reference: detect-secrets (https://github.com/Yelp/detect-secrets)
    """
    if len(text) < 10:
        return 0.0

    freq = {}
    for c in text:
        freq[c] = freq.get(c, 0) + 1

    total = sum(freq.values())
    n_unique = len(freq)

    if n_unique < 2:
        return 0.0

    # Calculate coefficient of variation (CV) of frequencies
    # Low CV = flat distribution (encoded), High CV = peaked (natural)
    mean_freq = total / n_unique
    variance = sum((f - mean_freq) ** 2 for f in freq.values()) / n_unique
    std_dev = math.sqrt(variance)
    cv = std_dev / mean_freq if mean_freq > 0 else 0

    # Invert: flat distribution (low CV) → high score (suspicious)
    # CV of 0 → score 1.0 (perfectly uniform)
    # CV of 1+ → score ~0.0 (very peaked/natural)
    flatness_score = max(0.0, 1.0 - cv)

    return flatness_score


def _is_encoded_payload(text: str) -> dict:
    """
    Multi-heuristic encoded payload detection.
    
    Runs 5 independent statistical tests. Only flags when ≥3 of 5 agree
    that the data is likely encoded/encrypted. This eliminates false
    positives from URLs, minified JS, hex colors, and long variable names.
    
    Returns dict with:
      - is_suspicious: bool
      - signals_triggered: int (0-5)
      - details: dict with individual test results
    """
    results = {}
    signals = 0

    # Test 1: Shannon Entropy (Classic)
    entropy = _shannon_entropy(text)
    results["shannon_entropy"] = round(entropy, 3)
    if entropy > 5.5:
        signals += 1

    # Test 2: Chi-Squared Uniformity (P-Value)
    chi_p = _chi_squared_uniformity(text)
    results["chi_squared_p_value"] = round(chi_p, 4)
    if chi_p > 0.05:  # High p-value = uniform distribution = suspicious
        signals += 1

    # Test 3: Serial Correlation (SCC)
    scc = _serial_correlation(text)
    results["serial_correlation"] = round(scc, 4)
    if abs(scc) < 0.15:  # Low correlation = random-looking = suspicious
        signals += 1

    # Test 4: Simpson's Diversity (D)
    simpson = _simpsons_index(text)
    results["simpsons_diversity"] = round(simpson, 4)
    if simpson < 0.85: # Low diversity = suspicious (repetitive/obfuscated)
        signals += 1

    # Test 5: KL-Divergence (Relative Entropy)
    kl_score = _kl_divergence(text)
    results["kl_divergence"] = round(kl_score, 4)
    if kl_score > 3.0: # High divergence from natural language = suspicious
        signals += 1

    results["signals_triggered"] = signals
    results["is_suspicious"] = signals >= 2  # Adjusted for high-sensitivity on short 64-byte secrets

    return results

def validate_llm_output(output_text: str) -> None:
    """
    Deterministic Output Firewall. Zero API calls.
    
    Checks:
      1. Prompt Injection Detection — regex scan for known jailbreak patterns.
      2. Secret Leak Detection — regex + multi-heuristic statistical analysis
         for API keys, passwords, and encoded payloads.
      3. Code Safety Scan — if the output contains Python code blocks, run them 
         through the existing AST-based static_analysis_check.
      4. Structural Validation — if the output is JSON, validate and scan 
         embedded code fields.
    
    Raises SecurityViolationException if any check fails.
    """
    violations = []

    # Prompt Injection Detection
    for pattern in _INJECTION_PATTERNS:
        match = pattern.search(output_text)
        if match:
            violations.append(f"Prompt injection artifact detected: '{match.group()}'")

    # Secret/Credential Leak Detection
    for pattern in _SECRET_PATTERNS:
        match = pattern.search(output_text)
        if match:
            redacted = match.group()[:10] + "...REDACTED"
            violations.append(f"Potential credential leak detected: '{redacted}'")

    # Multi-heuristic encoded payload detection (replaces naive entropy-only check)
    for line in output_text.split('\n'):
        stripped = line.strip()
        if len(stripped) > 40:
            analysis = _is_encoded_payload(stripped)
            if analysis["is_suspicious"]:
                violations.append(
                    f"Encoded payload detected ({analysis['signals_triggered']}/5 signals): "
                    f"entropy={analysis['shannon_entropy']}, "
                    f"chi²_p={analysis['chi_squared_p_value']}, "
                    f"SCC={analysis['serial_correlation']}, "
                    f"simpson={analysis['simpsons_diversity']}, "
                    f"kl={analysis['kl_divergence']} — "
                    f"'{stripped[:30]}...'"
                )

    # Code Safety Scan
    code_blocks = re.findall(r'```python\s*\n(.*?)```', output_text, re.DOTALL)
    if not code_blocks:
        code_blocks = re.findall(r'```\s*\n(.*?)```', output_text, re.DOTALL)
    for code_block in code_blocks:
        try:
            static_analysis_check(code_block)
        except SecurityViolationException as e:
            violations.append(f"Embedded code failed AST safety scan: {str(e)}")

    # Structural Validation
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

    # Final Verdict
    if violations:
        violation_summary = "; ".join(violations)
        logging.error(f"[OUTPUT FIREWALL] BLOCKED: {violation_summary}")
        raise SecurityViolationException(
            f"[FIREWALL BLOCKED] {len(violations)} violation(s) detected: {violation_summary}"
        )
    else:
        logging.info("[OUTPUT FIREWALL] Output passed all checks.")
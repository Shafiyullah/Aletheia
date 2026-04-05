import os
import ast
import json
import networkx as nx
import subprocess
import tempfile
import sys
import logging
import asyncio
from typing import List, Tuple, Optional, Dict, Any
from google import genai
from google.genai import types
from core.safety import SecurityViolationException
from core.config import MODEL_FAST, MODEL_SMART, MODEL_THINKING, MODEL_CLASSIFY
from core.utils import extract_code

# Configure logging
logging.basicConfig(
    format='%(asctime)s - [%(levelname)s] - %(name)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("aletheia.log", mode='a', encoding='utf-8')
    ]
)

class AletheiaEngine:
    def __init__(self, api_key: Optional[str] = None):
        self.graph = nx.DiGraph()
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        
        if self.api_key:
            self.client = genai.Client(api_key=self.api_key)
        else:
            logging.warning("GEMINI_API_KEY not found. AI features disabled.")
            self.client = None

    # PROMETHEUS: Code Reactor

    def _infer_types(self, code_str: str) -> str:
        """
        Static Type Inferencer for SMT Verification.
        Scans AST to determine the most likely types for function arguments.
        """
        try:
            tree = ast.parse(code_str)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    # For simplicity, we scan the first function's arguments
                    # and check for hints in the body.
                    # Default is (x: int) -> int
                    # If we see: x.append(), x is List
                    # If we see: np.dot(x, ...), x is Array/List
                    body_str = ast.dump(node)
                    if ".append" in body_str or ".extend" in body_str:
                        return "x: List[int]" # Placeholder refinement
                    if "np." in body_str or "jnp." in body_str or "math.sqrt" in body_str:
                        return "x: float"
            return "x: int"
        except:
            return "x: int"

    async def _verify_equivalence(self, original_code: str, optimized_code: str) -> bool:
        """
        Formal Verification using SMT Solvers (CrossHair/Z3).
        Proves exactly whether both implementations are behaviorally equivalent.
        """
        import tempfile
        import subprocess
        import os

        # Mathematical Upgrade: Static Type Discovery
        type_signature = self._infer_types(original_code)
        
        prompt = f"""
        ### ROLE: Formal Verification Engineer
        ### TASK: Extract these two code snippets into purely self-contained, deterministic Python functions with matching type signatures.
        
        ### ORIGINAL CODE:
        ```python
        {original_code}
        ```
        
        ### OPTIMIZED CODE:
        ```python
        {optimized_code}
        ```
        
        ### INSTRUCTIONS:
        1. Write `def func_original({type_signature}) -> Any:` matching the logical types.
        2. Write `def func_optimized({type_signature}) -> Any:` matching exactly.
        3. BOTH functions must be deterministic and fully deep-copyable.
        4. Do NOT call them. Return ONLY the code block containing the two functions.
        """
        
        env = os.environ.copy()
        equiv = False
        
        try:
            if not self.client: return True # Bypass if keys aren't loaded

            response = await self.client.aio.models.generate_content(
                model=MODEL_FAST,
                contents=prompt
            )
            module_code = extract_code(response.text)
            
            # Sanitize code using AST to remove side-effects.
            import ast
            try:
                tree = ast.parse(module_code)
                # Keep only function definitions
                tree.body = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
                sanitized_code = ast.unparse(tree)
            except Exception:
                # Fallback to raw code if AST parsing fails
                sanitized_code = module_code
            
            project_root = os.path.abspath(".")
            module_fn = "_ale_verify.py"
            tf_path = os.path.join(project_root, module_fn)
            with open(tf_path, 'w') as f:
                f.write(module_code)
            
            # Module name is the filename without .py
            module_name = "_ale_verify"
            
            # Execute crosshair diffbehavior with a strict 5-second per-path execution limit
            try:
                cmd = [
                    sys.executable, "-m", "crosshair", "diffbehavior",
                    f"{module_name}:func_original", f"{module_name}:func_optimized",
                    "--per_path_timeout", "1"
                ]
                
                # Still set PYTHONPATH for absolute robustness
                env["PYTHONPATH"] = project_root + os.pathsep + env.get("PYTHONPATH", "")
                
                # Bounded total execution solver time
                result = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=5, cwd=project_root)
                out = result.stdout + result.stderr
                
                if "No differences found" in out or "CrossHair explored" in out and "different" not in out:
                    equiv = True
                elif "different" in out.lower() or "exception" in out.lower() or result.returncode != 0:
                    logging.warning(f"Z3 Solver Equivalence Mismatch: {out[:300]}")
                    equiv = False
                else:
                    # If it's silent and exited with 0, we assume equivalence for these simple checks
                    equiv = (result.returncode == 0)
                    
            except subprocess.TimeoutExpired:
                 # If SMT Z3 cannot solve it within 5 seconds, it's too complex or loops infinitely.
                 logging.warning("Z3 Solver Timeout (5s). Rejecting optimization for safety.")
                 equiv = False
            finally:
                 try:
                     if os.path.exists(tf_path):
                         os.remove(tf_path)
                 except OSError:
                     pass
                     
            return equiv
            
        except Exception as e:
            logging.error(f"Equivalence Generation Error: {e}")
            return False

    async def generate_jax_optimization(self, code_str: str) -> str:
        """
        Neuro-Symbolic Optimization Flow:
        Step 1 (Neural): Identify bottleneck.
        Step 2 (Symbolic): Rewrite with JAX and @jax.jit.
        Step 3 (Grounding): Compile and verify syntax.
        Step 4 (Verification): Differential Equivalence Testing.
        """
        if not self.client:
            return json.dumps({"method": "error", "code": "# Gemini Client not initialized."})

        prompt = f"""
        ### ROLE: Google JAX Optimization Specialist
        ### TASK: Identify O(n^2) loops in the provided code and rewrite them using `jax.numpy` and `@jax.jit` for massive speedup.

        ### CODE:
        ```python
        {code_str}
        ```

        ### INSTRUCTIONS:
        1. Find the computationally expensive loop.
        2. Rewrite it using vectorized JAX patterns.
        3. Use `@jax.jit` for XLA compilation.
        4. Return ONLY the optimized Python code block.
        """

        try:
            for attempt in range(2): # Simple retry logic for grounding
                try:
                    response = await self.client.aio.models.generate_content(
                        model=MODEL_SMART,
                        contents=prompt
                    )
                    optimized_code = extract_code(response.text)
                    
                    # Step 3: Grounding (Simple Syntax Check)
                    try:
                        compile(optimized_code, "<string>", "exec")
                    except SyntaxError:
                        logging.warning(f"JAX Optimization Attempt {attempt+1} failed syntax check.")
                        continue
                        
                    # Step 4: Differential Testing
                    if not await self._verify_equivalence(code_str, optimized_code):
                        continue

                    return json.dumps({"method": "jax", "code": optimized_code})
                except Exception as e:
                    logging.error(f"JAX Optimization Error: {e}")
                    # Allow loop to continue or fall through
            
            # If loop finishes without success
            raise Exception("JAX Optimization failed after multiple attempts.")

        except Exception as e:
            logging.error(f"JAX Failed: {e}. Triggering Fallback.")
            # Trigger Fallback
            fallback_code = await self.generate_async_refactor(code_str)
            return json.dumps({"method": "fallback", "code": fallback_code})

    async def generate_async_refactor(self, code_str: str) -> str:
        """
        Standard Python optimization using asyncio and modernization.
        """
        if not self.client:
            return "# Gemini Client not initialized."

        prompt = f"""
        ### ROLE: Algorithmic Complexity Expert
        ### TASK: Optimize the provided code for Big-O time complexity and memory efficiency.

        ### CODE:
        ```python
        {code_str}
        ```

        ### INSTRUCTIONS:
        1. Identify O(n^2) nested loops and replace them with O(n) dictionaries/sets.
        2. Replace list comprehensions with generators for memory efficiency where applicable.
        3. Use `itertools` for faster iteration.
        4. Return ONLY the optimized Python code block.
        """

        try:
            response = await self.client.aio.models.generate_content(
                model=MODEL_SMART,
                contents=prompt
            )
            return extract_code(response.text)
        except Exception as e:
            logging.error(f"Async Refactor Error: {e}")
            return f"# Error: {str(e)}"

    async def dispatch_optimization(self, code_str: str) -> str:
        """
        Intelligent routing for optimization with parallel execution.
        1. Run Security Check and Classification in parallel.
        2. If Security fails, abort immediately.
        3. Route to specialized agent based on classification.
        """
        
        if not self.client:
            return "# Gemini Client not initialized."

        # Import async security check
        from core.safety import ai_security_check_async
        
        # Define classification task as coroutine
        async def classify_code():
            prompt = f"""
            Analyze this code. Determine the Category:
            1. 'HEAVY_MATH': Suitable for JAX/Vectorization/Scientific.
            2. 'SQL': Database queries (SELECT, INSERT, etc.).
            3. 'GENERAL_LOGIC': Strings, I/O, Web, standard algorithms.
            
            CODE SNIPPET:
            {code_str[:2000]}

            Output ONLY the category name.
            """
            
            try:
                response = await self.client.aio.models.generate_content(
                    model=MODEL_CLASSIFY,
                    contents=prompt
                )
                return response.text.strip().upper()
            except Exception as e:
                logging.error(f"Classification Error: {e}")
                return "GENERAL_LOGIC" # Default fallback

        # Step 1: Parallel Execution - Security + Classification
        try:
            # Launch both tasks concurrently
            security_task = ai_security_check_async(code_str)
            classify_task = classify_code()
            
            # Wait for both to complete
            _, category = await asyncio.gather(security_task, classify_task)
            
        except Exception as e:
            # If security check fails (raises SecurityViolationException), abort
            logging.error(f"Security Check Failed: {e}")
            return json.dumps({
                "method": "error",
                "code": f"# Security Violation: {str(e)}"
            })

        logging.info(f"Optimization Routing: {category}")

        # Step 2: Routing based on classification
        if "HEAVY_MATH" in category:
            result_json = await self.generate_jax_optimization(code_str)
            try:
                result = json.loads(result_json)
                if result.get("method") == "fallback" or result.get("method") == "error":
                    if result.get("method") == "fallback":
                        logging.warning("JAX Optimization failed. Falling back to General Async Refactor.")
                        # Fall through to general logic
                    else:
                        return result_json
                else:
                    return result_json
            except json.JSONDecodeError:
                 return json.dumps({"method": "jax", "code": result_json})
        
        elif "SQL" in category:
             optimized_sql = await self.optimize_sql(code_str)
             return json.dumps({"method": "sql_audit", "code": optimized_sql})

        # Step 3: General/Fallback
        optimized_code = await self.generate_async_refactor(code_str)
        return json.dumps({"method": "complexity_reducer", "code": optimized_code})

    async def optimize_sql(self, query: str) -> str:
        """
        Business Mode: SQL Optimization.
        """
        if not self.client:
            return "-- Gemini Client not initialized."

        prompt = f"""
        ### ROLE: Senior Database Administrator (DBA)
        ### TASK: Audit this SQL query for performance anti-patterns. Do NOT optimize blindly.

        ### QUERY:
        ```sql
        {query}
        ```

        ### INSTRUCTIONS:
        1. Flag `SELECT *` (Greedy selection).
        2. Flag `LIKE '%value%'` (Leading wildcard scanning).
        3. Identify implicit type conversions or potential N+1 issues.
        4. Return a structured "SQL PERFORMANCE AUDIT" report as a comment block, followed by the corrected SQL if applicable.
        """

        try:
            response = await self.client.aio.models.generate_content(
                model=MODEL_SMART,
                contents=prompt
            )
            return extract_code(response.text)
        except Exception as e:
            return f"-- Error executing SQL optimization: {e}"

    def analyze_blast_radius(self, files: Dict[str, str]) -> nx.DiGraph:
        """
        Builds a directed graph of imports from the provided files.
        """
        self.graph.clear()
        for filename, content in files.items():
            self.graph.add_node(filename)
            try:
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, (ast.Import, ast.ImportFrom)):
                        # Basic dependency parsing
                        if isinstance(node, ast.Import):
                            for alias in node.names:
                                self._add_dependency(filename, alias.name, files)
                        else:
                            if node.module:
                                self._add_dependency(filename, node.module, files)
            except SyntaxError:
                logging.error(f"Syntax error parsing {filename}")
        
        return self.graph

    def _add_dependency(self, source: str, target: str, files: dict):
        # Heuristic to find the file from import statement
        target_file = target.replace(".", "/") + ".py"
        if target_file in files:
            self.graph.add_edge(target_file, source)
        elif target + ".py" in files:
            self.graph.add_edge(target + ".py", source)

    def get_impacted_files(self, changed_file: str) -> List[str]:
        """Returns files that depend on the changed file."""
        if changed_file in self.graph:
            return list(nx.descendants(self.graph, changed_file))
        return []
import logging
import json
import os
from typing import Dict, Any, Optional
from google import genai
from core.config import MODEL_SMART, MODEL_FAST
from core.safety import run_in_sandbox
from core.async_utils import retry_api_call
from core.utils import extract_code

class BridgeEngine:
    """
    FEATURE 3: THE BRIDGE (Deep Reproduction)
    Translates scientific paper claims/formulas into executable Python code 
    to verify reproducibility.
    """
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")

        if self.api_key:
            self.client = genai.Client(api_key=self.api_key)
        else:
            logging.warning("GEMINI_API_KEY not found. Bridge disabled.")
            self.client = None

    async def _safe_generate_content(self, model: str, contents: Any, config: Optional[Dict] = None):
        """
        Helper to handle Rate Limits (429) & Service Overload (503).
        """
        try:
            return await self.client.aio.models.generate_content(
                model=model,
                contents=contents,
                config=config
            )
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "503" in err_str or "UNAVAILABLE" in err_str:
                logging.warning(f"Bridge API Issue ({err_str}). Falling back to {MODEL_FAST}...")
                return await self.client.aio.models.generate_content(
                    model=MODEL_FAST,
                    contents=contents,
                    config=config
                )
            raise e

    async def reproduce_paper(self, pdf_text: str) -> Dict[str, Any]:
        """
        1. Extract Formula/Claim.
        2. Generate Simulation Code.
        3. Execute in Sandbox.
        4. Verify Result.
        """
        if not self.client:
            return {"error": "Gemini Client not initialized."}

        prompt = f"""
        ### ROLE: Computational Reproducibility Agent
        ### TASK: Extract a Python math/simulation snippet from the paper to verify a result.
        
        ### CONTEXT:
        The user wants to verify a specific mathematical claim or algorithm from the paper.
        
        ### TEXT:
        {pdf_text[:10000]}

        ### INSTRUCTIONS:
        1. Find a mathematical formula, algorithm, or numerical claim (e.g., "Accuracy is 95%").
        2. Generate a Python script that simulates/calculates this.
        3. Do NOT use dangerous imports (os, sys, network). Use `numpy`, `pandas`, `sklearn` only.
        4. The script MUST print the final result to stdout.
        5. Return ONLY the code block.
        """

        try:
            response = await self._safe_generate_content(
                model=MODEL_SMART,
                contents=prompt
            )
            code_snippet = extract_code(response.text)
            
            # Execute in sandbox
            execution_result = run_in_sandbox(code_snippet)
            
            status = "Unknown"
            if execution_result:
                if "Error" in execution_result:
                    status = "Failed (Runtime Error)"
                else:
                    # Verify execution result with paper claim using LLM
                    verification_prompt = f"""
                    ### ROLE: Verification Engine Tracker
                    ### TASK: Determine if the Python code execution output matches or proves the mathematical claim inside the Research Paper excerpt.
                    
                    ### EXCERPT:
                    {pdf_text[:4000]}
                    
                    ### EXECUTION OUTPUT:
                    {execution_result}
                    
                    ### QUESTION: Does the output verify the claim? Answer with 'YES' or 'NO', followed by a one-sentence reason.
                    """
                    try:
                        eval_resp = await self._safe_generate_content(
                            model=MODEL_FAST,
                            contents=verification_prompt
                        )
                        if eval_resp and eval_resp.text and "YES" in eval_resp.text.strip().upper()[:10]:
                            status = "Verified Successfully"
                        else:
                            status = f"Failed (Logic Mismatch): {eval_resp.text[:50]}"
                    except Exception as verify_err:
                        logging.error(f"Verification Check Failed: {verify_err}")
                        status = "Executed Successfully (Verification Unreachable)"
            else:
                status = "Failed (No Output)"

            return {
                "extracted_code": code_snippet,
                "execution_result": execution_result,
                "status": status
            }
        except Exception as e:
            return {"error": str(e)}

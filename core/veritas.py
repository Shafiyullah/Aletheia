import logging
import asyncio
from typing import List, Dict, Any, Tuple, Optional
import PyPDF2
from google import genai
from core.config import MODEL_SMART, MODEL_FAST
from core.safety import run_in_sandbox, SecurityViolationException
from core.async_utils import retry_api_call

class VeritasAuditor:
    def __init__(self, api_key: Optional[str] = None, demo_mode: bool = False):
        import os # Ensure os is imported locally if needed, though file has it
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self.is_mock = demo_mode

        if self.api_key and not self.is_mock:
            self.client = genai.Client(api_key=self.api_key)
        else:
            self.client = None

    async def _safe_generate_content(self, model: str, contents: Any, config: Optional[Dict] = None):
        """
        Helper wrapper to handle Rate Limits (429) by falling back to Flash.
        """
        try:
            return await self.client.aio.models.generate_content(
                model=model,
                contents=contents,
                config=config
            )
        except Exception as e:
            # Check for Rate Limit (429) or Service Overload (503)
            err_str = str(e)
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "503" in err_str or "UNAVAILABLE" in err_str:
                logging.warning(f"API Issue ({err_str}) on {model}. Falling back to {MODEL_FAST}...")
                print(f"⚠️ API Issue on {model}. Switching to {MODEL_FAST}...") 
                return await self.client.aio.models.generate_content(
                    model=MODEL_FAST,
                    contents=contents,
                    config=config
                )
            raise e

    def extract_text_from_pdf(self, file_obj) -> str:
        """Extracts text from a PDF file object."""
        try:
            reader = PyPDF2.PdfReader(file_obj)
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
            return text
        except Exception as e:
            logging.error(f"PDF Extraction Error: {e}")
            return f"Error extracting PDF: {str(e)}"

    async def audit_pdf(self, pdf_text: str) -> List[Dict[str, Any]]:
        """
        Chain-of-Verification (CoVe) for PDF audit.
        1. Extract Claims.
        2. Extract Citations.
        3. Verify Claims against Citations.
        """
        if self.is_mock:
            return [{
                "claim": "[DEMO] The Earth is Flat.",
                "citation": "Ancient Maps (1500)",
                "verification": "NO",
                "evidence": "[DEMO] Satellite imagery confirms spherical shape."
            }]

        if not self.client:
            return [{"error": "Gemini Client not initialized."}]

        prompt = f"""
        ### ROLE: Research Integrity Auditor
        ### TASK: Perform a Chain-of-Verification (CoVe) audit on the provided research paper text.

        ### TEXT:
        {pdf_text[:10000]} # Limit text for prompt constraints

        ### PROTOCOL:
        1. Identify 3-5 major scientific claims made in the paper.
        2. Identify the specific citation (source/author/year) provided for each claim.
        3. Analyze if the text provided actually supports the claim.

        ### OUTPUT FORMAT (JSON):
        [
          {{
            "claim": "string",
            "citation": "string",
            "verification": "YES/NO",
            "evidence": "Short explanation of why it matches or fails."
          }}
        ]
        """

        try:
            response = await self._safe_generate_content(
                model=MODEL_SMART,
                contents=prompt,
                config={'response_mime_type': 'application/json'}
            )
            # Handle potential JSON extraction issues
            response_text = response.text.strip()
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            
            return json.loads(response_text)
        except Exception as e:
            logging.error(f"Audit PDF Error: {e}")
            return [{"error": str(e)}]



    @retry_api_call()
    async def verify_claim_cove(self, claim: str, source_text: str) -> Dict[str, Any]:
        """
        Implements Chain-of-Verification (CoVe) to reduce hallucinations.
        Standard Prompt: "Is this true?" -> Hallucinates.
        CoVe Prompt: "Draft -> Verify Facts -> Final Answer" -> High Accuracy.
        """
        if not self.client:
             return {"error": "Gemini Client not initialized.", "verdict": "ERROR"}

        prompt = f"""
        ### ROLE: Senior Research Verifier (CoVe Protocol)
        ### TASK: Verify the specific CLAIM against the SOURCE TEXT with extreme rigor.

        ### CLAIM:
        "{claim}"

        ### SOURCE TEXT:
        {source_text[:15000]} # Context Window Limit

        ### INSTRUCTIONS (Chain-of-Verification):
        
        Step 1: DRAFT a preliminary answer based *only* on the text.
        Step 2: Identify specific FACTS in your draft that need verification (dates, numbers, names).
        Step 3: CHECK these facts against the source text. If a fact is not present, mark it as UNSUPPORTED.
        Step 4: Formulate the Final Verdict.

        ### OUTPUT FORMAT (JSON ONLY):
        {{
            "step_1_draft": "string",
            "step_2_verification_points": ["fact1", "fact2"],
            "step_3_corrections": "string (if any)",
            "verdict": "TRUE" | "FALSE" | "PARTIALLY_TRUE" | "UNSUPPORTED",
            "confidence": 0.0 to 1.0,
            "reasoning": "Final explanation citing the text.",
            "citations": ["quote from text"]
        }}
        """

        try:
            response = await self._safe_generate_content(
                model=MODEL_SMART,
                contents=prompt,
                config={'response_mime_type': 'application/json'}
            )
            
            # Robust JSON parsing
            text = response.text.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                 text = text.split("```")[1].split("```")[0].strip()
            
            return json.loads(text)

        except Exception as e:
            logging.error(f"CoVe Verification Error: {e}")
            return {
                "verdict": "ERROR",
                "reasoning": f"System Error: {str(e)}",
                "confidence": 0.0
            }

    def _extract_code(self, text: str) -> str:
        if "```python" in text:
            return text.split("```python")[1].split("```")[0].strip()
        elif "```" in text:
            return text.split("```")[1].split("```")[0].strip()
        return text.strip()
import json # Added missing import

import logging
import asyncio
import json
import os
import re
from typing import List, Dict, Any, Tuple, Optional, Set
import PyPDF2
from google import genai
from core.config import MODEL_SMART, MODEL_FAST
from core.safety import run_in_sandbox, SecurityViolationException
from core.async_utils import retry_api_call
from core.utils import extract_code

class VeritasAuditor:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")

        if self.api_key:
            self.client = genai.Client(api_key=self.api_key)
        else:
            self.client = None
            logging.warning("GEMINI_API_KEY not found. Veritas Audit will fail.")

    async def _safe_generate_content(self, model: str, contents: Any, config: Optional[Dict] = None):
        """
        Helper wrapper to handle Rate Limits (429) by falling back to Flash.
        """
        if not self.client:
             raise ValueError("Gemini Client not initialized.")

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

    # --- Span-Level Verification (Deterministic, No LLM) ---

    @staticmethod
    def _extract_ngrams(text: str, n: int) -> Set[str]:
        """Extract character n-grams from text."""
        text = text.lower()
        return {text[i:i+n] for i in range(len(text) - n + 1)} if len(text) >= n else {text}

    @staticmethod
    def _jaccard_similarity(set_a: Set[str], set_b: Set[str]) -> float:
        """Jaccard similarity between two sets. Returns 0.0-1.0."""
        if not set_a or not set_b:
            return 0.0
        intersection = set_a & set_b
        union = set_a | set_b
        return len(intersection) / len(union)

    @staticmethod
    def _extract_reference_section(source_text: str) -> str:
        """
        Extracts the References/Bibliography section from academic text.
        Falls back to the last 20% of the document if no header is found.
        """
        patterns = [
            r'(?i)\n\s*references\s*\n',
            r'(?i)\n\s*bibliography\s*\n',
            r'(?i)\n\s*works\s+cited\s*\n',
            r'(?i)\n\s*literature\s+cited\s*\n',
        ]
        for pattern in patterns:
            match = re.search(pattern, source_text)
            if match:
                return source_text[match.start():]
        cutoff = int(len(source_text) * 0.8)
        return source_text[cutoff:]

    @staticmethod
    def _extract_numbers(text: str) -> Set[str]:
        """Extracts all numerical values and percentages from text."""
        return set(re.findall(r'\d+(?:\.\d+)?(?:%|x)?', text))

    def span_level_verify(self, claim_results: List[Dict[str, Any]], source_text: str) -> List[Dict[str, Any]]:
        """
        Deterministic Span-Level Verification (SLV).
        
        Runs three independent checks on each "YES" claim:
          1. Citation Grounding — Does the cited author/source appear in the
             document's reference section?
          2. Claim-Source Overlap — N-gram Jaccard similarity between the claim
             and actual source text. Catches fabricated language.
          3. Numerical Anchoring — Do specific numbers/percentages in the claim 
             exist in the source?
             
        Each check produces a 0.0-1.0 score. Combined weighted score below the
        threshold triggers rejection.
        """
        REJECTION_THRESHOLD = 0.15
        verified_results = []

        # Pre-compute once for all claims
        normalized_source = " ".join(source_text.split()).lower()
        source_ngrams = self._extract_ngrams(normalized_source, 4)
        source_numbers = self._extract_numbers(normalized_source)
        ref_section = self._extract_reference_section(source_text).lower()

        for res in claim_results:
            if res.get("verification") != "YES":
                verified_results.append(res)
                continue

            claim_text = res.get("claim", "")
            citation = res.get("citation", "")
            rejection_reasons = []

            # --- Check 1: Citation Grounding (weight: 0.4) ---
            citation_score = 0.0
            if citation and citation != "No citation":
                common_words = {'the', 'and', 'for', 'from', 'with', 'that', 'this', 'research', 'paper', 'study'}
                citation_tokens = [
                    w.strip('().,;:') for w in citation.split()
                    if len(w.strip('().,;:')) > 2 and w.strip('().,;:').lower() not in common_words
                ]
                if citation_tokens:
                    matched = sum(1 for t in citation_tokens if t.lower() in ref_section)
                    citation_score = matched / len(citation_tokens)
                if citation_score < 0.3:
                    rejection_reasons.append(
                        f"Citation '{citation}' not found in document references "
                        f"(match: {citation_score:.0%})"
                    )
            else:
                citation_score = 0.0
                rejection_reasons.append("No citation provided for a verified claim")

            # --- Check 2: Claim-Source N-gram Overlap (weight: 0.35) ---
            claim_ngrams = self._extract_ngrams(claim_text.lower(), 4)
            overlap_score = self._jaccard_similarity(claim_ngrams, source_ngrams)
            scaled_overlap = min(overlap_score / 0.02, 1.0)
            if scaled_overlap < 0.3:
                rejection_reasons.append(
                    f"Claim language has very low overlap with source text "
                    f"(Jaccard: {overlap_score:.4f})"
                )

            # --- Check 3: Numerical Anchoring (weight: 0.25) ---
            claim_numbers = self._extract_numbers(claim_text)
            if claim_numbers:
                anchored = claim_numbers & source_numbers
                number_score = len(anchored) / len(claim_numbers)
                if number_score < 0.5:
                    unanchored = claim_numbers - source_numbers
                    rejection_reasons.append(
                        f"Numbers {unanchored} in claim not found in source document"
                    )
            else:
                number_score = 1.0

            # --- Combined Score ---
            combined = (citation_score * 0.4) + (scaled_overlap * 0.35) + (number_score * 0.25)

            if combined < REJECTION_THRESHOLD:
                res["verification"] = "NO"
                res["slv_score"] = round(combined, 3)
                res["evidence"] = (
                    f"[SLV REJECTED] (score: {combined:.3f}/{REJECTION_THRESHOLD}). "
                    f"Reasons: {'; '.join(rejection_reasons)}"
                )
                logging.warning(
                    f"SLV rejected claim: '{claim_text[:60]}...' "
                    f"(score={combined:.3f}, reasons={rejection_reasons})"
                )
            else:
                res["slv_score"] = round(combined, 3)

            verified_results.append(res)

        return verified_results

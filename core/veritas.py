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

    # Span-Level Verification (Deterministic, No LLM)

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
        return source_text[int(len(source_text) * 0.8):]

    @staticmethod
    def _extract_numbers(text: str) -> Set[str]:
        """Extracts all numerical values and percentages from text."""
        return set(re.findall(r'\d+(?:\.\d+)?(?:%|x)?', text))

    def _proximity_score(self, query: str, source: str) -> float:
        """
        Calculates a proximity-weighted similarity score.
        """
        words = [w.lower() for w in re.findall(r'\w+', query) if len(w) > 3]
        if not words: return 1.0
        
        source_words = [w.lower() for w in re.findall(r'\w+', source)]
        word_indices = {}
        for i, w in enumerate(source_words):
            if w in words:
                word_indices.setdefault(w, []).append(i)
        
        if len(word_indices) < 2:
            return 0.5 if word_indices else 0.0

        min_window = float('inf')
        present_words = list(word_indices.keys())
        for i in range(len(present_words)):
            for j in range(i + 1, len(present_words)):
                indices_a = word_indices[present_words[i]]
                indices_b = word_indices[present_words[j]]
                for idx_a in indices_a:
                    for idx_b in indices_b:
                        min_window = min(min_window, abs(idx_a - idx_b))
        
        if min_window <= 10: return 1.0
        if min_window >= 100: return 0.0
        return 1.0 - (min_window / 100)

    def span_level_verify(self, claim_results: List[Dict[str, Any]], source_text: str) -> List[Dict[str, Any]]:
        """
        Deterministic Span-Level Verification (SLV).
        """
        REJECTION_THRESHOLD = 0.25 
        verified_results = []

        normalized_source = " ".join(source_text.split()).lower()
        source_ngrams = self._extract_ngrams(normalized_source, 4)
        source_numbers = self._extract_numbers(normalized_source)
        ref_section = self._extract_reference_section(source_text).lower()

        for res in claim_results:
            if res.get("verification") != "YES":
                verified_results.append(res)
                continue

            claim_text = str(res.get("claim", ""))
            citation = str(res.get("citation", "")).lower()
            rejection_reasons = []

            # 1. Citation Grounding
            cit_score = 1.0 if citation in ref_section or any(p in ref_section for p in citation.split() if len(p) > 2) else 0.0
            if cit_score < 1.0:
                rejection_reasons.append(f"Citation '{citation}' not found in references.")

            # 2. Semantic Overlap
            claim_ngrams = self._extract_ngrams(claim_text.lower(), 4)
            overlap_score = self._jaccard_similarity(claim_ngrams, source_ngrams)
            if overlap_score < 0.01:
                rejection_reasons.append("Low semantic overlap with source.")

            # 3. Numerical Anchoring
            claim_nums = self._extract_numbers(claim_text)
            num_score = 1.0 if not claim_nums else (len(claim_nums & source_numbers) / len(claim_nums))
            if num_score < 1.0:
                rejection_reasons.append("Numerical data in claim not found in source.")

            # 4. Proximity Weighted Support
            prox_score = self._proximity_score(claim_text, normalized_source)

            # Weighting: Citation(0.3), Overlap(0.3), Numbers(0.2), Proximity(0.2)
            combined = (cit_score * 0.3) + (min(overlap_score / 0.02, 1.0) * 0.3) + (num_score * 0.2) + (prox_score * 0.2)
            
            res["slv_score"] = round(combined, 3)
            if combined < REJECTION_THRESHOLD:
                res["verification"] = "NO"
                res["evidence"] = f"[SLV REJECTED] Score: {res['slv_score']}. Reasons: {'; '.join(rejection_reasons)}"
            
            verified_results.append(res)

        return verified_results

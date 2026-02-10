import os
import io
import logging
from typing import List, Dict, Any, Optional
from PIL import Image
from google import genai
from core.config import MODEL_VISION

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [%(levelname)s] - %(name)s - %(message)s')

# Try importing pdf2image, handle missing dependency gracefully
try:
    from pdf2image import convert_from_bytes
    PDF2IMAGE_AVAILABLE = True
except ImportError:
    PDF2IMAGE_AVAILABLE = False
    logging.warning("pdf2image not installed. Vision Parsing will fail. Please install poppler and pdf2image.")

class VisionParser:
    def __init__(self):
        self.api_key = os.environ.get("GEMINI_API_KEY")
        if self.api_key:
            self.client = genai.Client(api_key=self.api_key)
        else:
            self.client = None
            logging.warning("GEMINI_API_KEY not found. Vision features disabled.")

    @staticmethod
    def convert_pdf_to_images(pdf_bytes: bytes) -> List[Image.Image]:
        """
        Converts PDF bytes to a list of PIL Images using pdf2image.
        Requires Poppler installed on the system.
        """
        if not PDF2IMAGE_AVAILABLE:
            raise ImportError("pdf2image library is not installed.")

        try:
            # Convert PDF to images (300 DPI for better OCR)
            images = convert_from_bytes(pdf_bytes, dpi=300)
            return images
        except Exception as e:
            logging.error(f"Error converting PDF to images: {e}")
            if "poppler" in str(e).lower():
                raise ImportError("Poppler is not installed or not in PATH. Please install Poppler.")
            raise e

    async def extract_features_with_vision(self, images: List[Image.Image]) -> str:
        """
        Sends images to Gemini Vision for transcription using Vision-First approach.
        Optimized for tokens: Scans Abstract (Pg 1) and Conclusion (Last Pg) if > 5 pages.
        """
        if not self.client:
            return "Error: Gemini Client not available."

        if not images:
            return "Error: No images provided."

        # Optimization Strategy
        pages_to_process = []
        if len(images) > 5:
            logging.info(f"PDF has {len(images)} pages. Optimizing: Scanning Page 1 (Abstract) and Last Page (Conclusion).")
            # Create a composite image or list of key pages
            # For this implementation, we'll process them as a list of images provided to the model
            pages_to_process = [images[0], images[-1]]
            status_msg = f"**Note:** Processed Page 1 and Page {len(images)} (Abstract & Conclusion) to save resources."
        else:
            logging.info(f"PDF has {len(images)} pages. Scanning full document.")
            pages_to_process = images
            status_msg = ""
            
        prompt = """
        ### ROLE: Scientific Document Transcriber
        ### TASK: Transcribe this document exactly.
        
        ### INSTRUCTIONS:
        1. **Math Formulas:** Convert ALL math formulas to LaTeX format (using $...$ for inline and $$...$$ for block).
        2. **Tables:** Preserve ALL tables and represent them using Markdown table syntax.
        3. **Structure:** Maintain the original headings and structure.
        4. **Content:** Do NOT summarize. Transcribe the text exactly as it appears.
        
        ### OUTPUT:
        Return the Markdown transcription.
        """

        try:
            # Prepare contents for Gemini (List of Prompt + Images)
            # We resize images if they are massive to avoid payload limits, though Gemini is robust.
            
            processed_contents = [prompt]
            for img in pages_to_process:
                # Gemini Client expects PIL images directly or bytes
                processed_contents.append(img)
            
            logging.info(f"Sending request to {MODEL_VISION}...")
            
            try:
                # Primary Attempt: Pro Model
                response = await self.client.aio.models.generate_content(
                    model=MODEL_VISION,
                    contents=processed_contents
                )
                return f"{status_msg}\n\n{response.text}"
            
            except Exception as e:
                # Check for Rate Limit (429) or other API errors
                # Check string representation of error for 429
                err_str = str(e)
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                    logging.warning(f"Rate Limit Hit on {MODEL_VISION}. Falling back to Flash...")
                    st_msg = "**⚠️ Pro API Quota Exceeded. Switched to 'gemini-3-flash-preview' (Faster, Higher Limits).**"
                    
                    # Fallback: Flash Model
                    fallback_model = "gemini-3-flash-preview"
                    try:
                        response = await self.client.aio.models.generate_content(
                            model=fallback_model,
                            contents=processed_contents
                        )
                        return f"{status_msg}\n\n{st_msg}\n\n{response.text}"
                    except Exception as flash_err:
                        return f"Error: Both Pro and Flash models failed. {flash_err}"
                else:
                    raise e # Re-raise if not rate limit

        except Exception as e:
            logging.error(f"Vision Feature Extraction Error: {e}")
            return f"Error extracting features: {e}. Try disabling 'Vision-First Parsing' to use standard text extraction."

# Standalone helper function for easy import
vision_parser = VisionParser()

async def parse_research_paper(pdf_bytes: bytes) -> str:
    """
    Main entry point: Bytes -> Images -> Transcription
    """
    try:
        images = vision_parser.convert_pdf_to_images(pdf_bytes)
        transcription = await vision_parser.extract_features_with_vision(images)
        return transcription
    except ImportError as e:
        return f"Configuration Error: {e}"
    except Exception as e:
        return f"Parsing Error: {e}"

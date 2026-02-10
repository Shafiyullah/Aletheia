import asyncio
import sys
import os

# Add root to sys.path to allow importing 'core'
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.vision_parser import vision_parser, parse_research_paper
from data.demo_repo import DEMO_PDF_CONTENT

async def test_vision_parser():
    print("--- Testing Vision-First PDF Parser ---\n")

    # 1. Test Dependency Check
    try:
        from pdf2image import convert_from_bytes
        print("✅ pdf2image is installed.")
    except ImportError:
        print("⚠️ pdf2image is NOT installed. Test will likely fail or use mock.")

    # 2. Test Processing
    # Create a minimal valid PDF for testing (pdf2image requires valid PDF structure)
    # This is a 1-page blank PDF
    MINIMAL_PDF_BYTES = b"%PDF-1.0\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj 3 0 obj<</Type/Page/MediaBox[0 0 3 3]/Parent 2 0 R/Resources<<>>>>endobj xref\n0 4\n0000000000 65535 f\n0000000010 00000 n\n0000000060 00000 n\n0000000117 00000 n\ntrailer<</Size 4/Root 1 0 R>>startxref\n223\n%%EOF"
    
    print(f"Input PDF Size: {len(MINIMAL_PDF_BYTES)} bytes")
    
    result = await parse_research_paper(MINIMAL_PDF_BYTES)
    
    print("\n--- Transcription Result ---")
    print(result[:500] + "..." if len(result) > 500 else result)
    
    if "Error" not in result and "Configuration Error" not in result:
        print("\nPASS: Vision Parsing initiated successfully.")
    elif "Poppler" in result:
        print("\nWARN: Poppler missing (Expected on some environments). Logic handled gracefully.")
    else:
        print(f"\nFAIL: Unexpected error: {result}")

if __name__ == "__main__":
    asyncio.run(test_vision_parser())

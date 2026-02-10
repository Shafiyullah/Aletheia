import PyPDF2
import io
import os
from PIL import Image
from google import genai
from core.config import MODEL_VISION

def extract_images_from_pdf(pdf_stream):
    """
    Extracts all images from a PDF file stream using PyPDF2.
    Returns a list of PIL Image objects.
    """
    try:
        reader = PyPDF2.PdfReader(pdf_stream)
        images = []
        for page in reader.pages:
            if '/Resources' in page and '/XObject' in page['/Resources']:
                xObject = page['/Resources']['/XObject'].get_object()
                for obj in xObject:
                    if xObject[obj]['/Subtype'] == '/Image':
                        try:
                            img_data = xObject[obj].get_data()
                            # Try to create PIL image
                            image = Image.open(io.BytesIO(img_data))
                            images.append(image)
                        except Exception as e:
                            # print(f"Failed to extract image: {e}")
                            pass
                            
        return images
    except Exception as e:
        print(f"Error reading PDF: {e}")
        return []

def audit_visual_integrity(images):
    """
    Sends images to Gemini 3 Pro Vision to detect fraud.
    """
    if not images:
        return "No images detected."

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return "GEMINI_API_KEY not found."

    client = genai.Client(api_key=api_key)
    
    # We send a collage or batch of images to the model
    prompt = """
    ROLE: Scientific Image Forensics Expert.
    TASK: Analyze these extracted figures from a research paper.
    
    LOOK FOR:
    1. Duplication: Are two figures identical but labeled differently?
    2. Manipulation: Signs of rotation, splicing, or clone-stamping.
    3. Inconsistency: Do the error bars look hand-drawn?
    
    OUTPUT:
    Return a JSON Risk Report: { "suspicious_figures": [], "risk_score": 0-100 }
    """
    try:
        try:
            # Note: In production, we might limit this to the first 5 images to save tokens
            # Using MODEL_VISION from config
            print(f"DEBUG: Using model: {MODEL_VISION}")
            response = client.models.generate_content(
                model=MODEL_VISION,
                contents=[prompt, *images[:10]] 
            )
            return response.text
        except Exception as e:
            print(f"DEBUG: Primary model failed ({e}). Trying fallback...")
            # Fallback to gemini-3-flash-preview
            response = client.models.generate_content(
                model="gemini-3-flash-preview",
                contents=[prompt, *images[:10]] 
            )
            return response.text
    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"Error in visual audit: {str(e)}"

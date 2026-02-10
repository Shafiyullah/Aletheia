try:
    print("Importing fitz...", flush=True)
    import fitz
    print("fitz imported successfully.", flush=True)
except Exception as e:
    print(f"Failed to import fitz: {e}", flush=True)

try:
    print("Importing PIL...", flush=True)
    from PIL import Image
    print("PIL imported successfully.", flush=True)
except Exception as e:
    print(f"Failed to import PIL: {e}", flush=True)

try:
    print("Importing google.genai...", flush=True)
    from google import genai
    print("google.genai imported successfully.", flush=True)
except Exception as e:
    print(f"Failed to import google.genai: {e}", flush=True)

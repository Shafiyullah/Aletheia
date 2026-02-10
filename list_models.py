import google.generativeai as genai
import os

api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    print("Error: GEMINI_API_KEY not found.")
else:
    genai.configure(api_key=api_key)
    try:
        models = list(genai.list_models())
        with open("models.txt", "w") as f:
            for m in models:
                f.write(f"{m.name}\n")
                if 'generateContent' in m.supported_generation_methods:
                    print(f"Supported Code Model: {m.name}")
        print("Models saved to models.txt")
    except Exception as e:
        print(f"Error listing models: {e}")

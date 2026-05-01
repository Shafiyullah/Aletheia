import os

# GEMINI API KEY 
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get(
        "ALLOWED_ORIGINS", "http://localhost:8501"
    ).split(",")
]

# MODEL TIER DEFINITIONS

# TIER 1: THE SCANNER 
MODEL_FAST = "gemini-3-pro-preview"

# Tier 2: 
MODEL_SMART = "gemini-3-pro-preview"

# Tier 3: 
MODEL_THINKING = "gemini-3-pro-preview" 

# Tier 4: SPECIALIZED AGENTS
MODEL_CLASSIFY = "gemini-3-pro-preview"
MODEL_VISION = "gemini-3-pro-preview"
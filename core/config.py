import os

# TIER 1: THE SCANNER (Fast, Cheap, 1M+ Context)
# Use this for: Dependency Graphs, File Parsing, "Blast Radius" calculation.
MODEL_FAST = "gemini-3-flash-preview"

# Tier 2: THE THINKER (Strong Reasoning, Pro level)
# Use this for: Fixing Code, Generating Tests, Judiciary reviews, Reasoning steps.
MODEL_SMART = "gemini-3-pro-preview"

# Tier 3: THE PROVER (Thinking model for complex logic)
# Use this for: Deep Reasoning, verifying complex fixes.
MODEL_THINKING = "gemini-3-pro-preview" 

# Tier 4: SPECIALIZED AGENTS
MODEL_CLASSIFY = "gemini-3-flash-preview"
MODEL_VISION = "gemini-3-pro-preview"


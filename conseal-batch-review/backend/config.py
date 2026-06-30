"""
Application configuration.

USE_LOCAL_LLM_TIER controls whether the Tier 2 LLM detection uses:
  - False (default): Pre-generated fixture data from the synthetic data generator
  - True: Live local API calls (e.g. Ollama running Gemma E4B)

To switch to live mode:
  1. Set USE_LOCAL_LLM_TIER = True
  2. Set OLLAMA_URL if different from default
"""

import os

# --- Feature Flags ---
USE_LOCAL_LLM_TIER: bool = os.environ.get("USE_LOCAL_LLM_TIER", "true").lower() == "true"

# --- Database ---
DATABASE_PATH: str = os.environ.get("DATABASE_PATH", os.path.join(os.path.dirname(__file__), "conseal.db"))

# --- Local LLM (only used when USE_LOCAL_LLM_TIER=True) ---
OLLAMA_URL: str = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL: str = os.environ.get("OLLAMA_MODEL", "gemma4:e4b")

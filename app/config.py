"""
config.py — Centralized environment configuration for FinQuery.

Loads and validates all environment variables once at import time.
No other module should call os.getenv() directly — everything
flows through this file so there's a single source of truth and
a single point of failure if a variable is missing.
"""

import os
from dotenv import load_dotenv

load_dotenv()


def _require(key: str) -> str:
    """Fetch a required env var or fail fast with a clear error."""
    value = os.getenv(key)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {key}")
    return value


# --- Read-only app connection (Streamlit + LangChain) ---
DB_HOST = _require("DB_HOST")
DB_PORT = _require("DB_PORT")
DB_NAME = _require("DB_NAME")
DB_USER = _require("DB_USER")
DB_PASSWORD = _require("DB_PASSWORD")

# --- Gemini ---
GOOGLE_API_KEY = _require("GOOGLE_API_KEY")

# --- Privileged connection (MOLAP refresh only — used only by scripts/refresh_molap.py) ---
MOLAP_REFRESH_DB_USER = os.getenv("MOLAP_REFRESH_DB_USER")
MOLAP_REFRESH_DB_PASSWORD = os.getenv("MOLAP_REFRESH_DB_PASSWORD")
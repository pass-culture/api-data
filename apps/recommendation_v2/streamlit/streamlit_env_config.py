"""
Streamlit environment configuration.

Single source of truth for every value used by the Streamlit app that depends on the
targeted environment (stg / prod): GCP project, BigQuery dataset, backend / app / backoffice URLs.

NOTE: this module is specific to the Streamlit app. It is NOT related to
`src/config/settings.py`, which configures the FastAPI recommendation API.

The target environment is derived from `GCP_PROJECT`, read from the app's `.env`
(apps/recommendation_v2/.env).
"""

import os
from pathlib import Path

from dotenv import load_dotenv


# --- 1. .env loading ---
DOTENV_PATH = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(DOTENV_PATH, override=True)


# --- 2. Targeted environment ---
GCP_PROJECT = os.environ.get("GCP_PROJECT", "passculture-data-ehp")
GCP_PROJECT_TO_ENV = {
    "passculture-data-ehp": "stg",
    "passculture-data-prod": "prod",
}
ENV_SHORT_NAME = GCP_PROJECT_TO_ENV.get(GCP_PROJECT, "stg")
# Key used to pick per-environment values below (anything other than prod is treated as stg).
ENV_KEY = "prod" if ENV_SHORT_NAME == "prod" else "stg"


# Substrings identifying a local API URL (the only case where the DB is directly reachable).
LOCAL_HOST_PATTERNS = ("localhost", "127.0.0.", "0.0.0.0")

# Deployment environment set by the Makefile (fallback to detect the targeted API env).
DEPLOY_ENV = os.environ.get("DEPLOY_ENV", "").lower()

# Remote recommendation API settings (v1 legacy / v2 default) and auth token.
REMOTE_API_V1_URL = os.environ.get("REMOTE_API_V1_URL", "")
REMOTE_API_URL = os.environ.get("REMOTE_API_URL", "")
REMOTE_API_TOKEN = os.environ.get("REMOTE_API_TOKEN", "")


# --- 3. BigQuery ---
BIGQUERY_DATASET_NAME = f"analytics_{ENV_SHORT_NAME}"


# --- 4. Base URLs per environment ---
_BACKEND_BASE_URLS = {
    "stg": "https://backend.staging.passculture.team",
    "prod": "https://backend.passculture.app",
}
_WEBAPP_BASE_URLS = {
    "stg": "https://app.staging.passculture.team",
    "prod": "https://passculture.app",
}
_BACKOFFICE_BASE_URLS = {
    "stg": "https://backoffice.staging.passculture.team",
    "prod": "https://backoffice.passculture.team",
}

BACKEND_BASE_URL = _BACKEND_BASE_URLS[ENV_KEY]
WEBAPP_BASE_URL = _WEBAPP_BASE_URLS[ENV_KEY]
BACKOFFICE_BASE_URL = _BACKOFFICE_BASE_URLS[ENV_KEY]

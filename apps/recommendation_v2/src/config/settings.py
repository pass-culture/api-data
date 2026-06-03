"""
Centralized Configuration Module.

This module loads environment variables from a .env file (if present) and
exposes them as strictly typed Python constants. It acts as the single source
of truth for all external configurations (Database, GCP, Logging, etc.).
"""

import logging
import os
from pathlib import Path

from dotenv import load_dotenv


# --- 1. Environment Loading ---
# Resolve the path to the .env file located at the root of the src directory
environment_file_path = Path(".env")
load_dotenv(dotenv_path=environment_file_path, override=False)


# --- 2. Application Environment ---
ENV: str = os.environ.get("ENV", "local")

IS_LOCAL: bool = ENV in ("local", "ci")
IS_TESTING: bool = ENV == "testing"
IS_STAGING: bool = ENV == "staging"
IS_PROD: bool = ENV == "production"
IS_CI: bool = ENV == "ci"

# Fail-fast mechanism: prevent the app from starting if the environment is unrecognized
if ENV not in ("local", "testing", "staging", "production", "ci"):  # pragma: no cover
    raise RuntimeError(f"Unknown environment detected: {ENV}")

FASTAPI_SERVER_PORT: int = int(os.environ.get("FASTAPI_SERVER_PORT", "8000"))

RECOMMENDATION_API_VERSION = 2


# --- 3. Logging Configuration ---
# Reduce log noise in production by defaulting to INFO level
LOG_LEVEL: int = logging.INFO if IS_PROD else logging.DEBUG

LOGS_PRETTY_PRINT: bool = bool(int(os.environ.get("LOGS_PRETTY_PRINT", "1")))


# --- 4. Database Configuration (SQL/PostgreSQL) ---
SQL_BASE_DATABASE: str = os.environ.get("SQL_BASE", "")
SQL_BASE_USER: str = os.environ.get("SQL_BASE_USER", "")
SQL_BASE_PASSWORD: str = os.environ.get("SQL_BASE_PASSWORD", "")
SQL_BASE_PORT: str = os.environ.get("SQL_PORT", "5439")
SQL_BASE_HOST: str = os.environ.get("SQL_HOST", "localhost")

API_TOKEN: str = os.environ.get("API_TOKEN", "")

# Construct the async SQLAlchemy connection string
DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}".format(
        DB_USER=SQL_BASE_USER,
        DB_PASSWORD=SQL_BASE_PASSWORD,
        DB_HOST=f"{SQL_BASE_HOST}:{SQL_BASE_PORT}",
        DB_NAME=SQL_BASE_DATABASE,
    ),
)


# --- 5. Google Cloud Platform & Vertex AI ---
GCP_PROJECT: str = os.environ.get("GCP_PROJECT", "passculture-data-ehp")

VERTEX_RETRIEVAL_ENDPOINT_NAME: str = os.environ.get(
    "VERTEX_RETRIEVAL_ENDPOINT_NAME", "recommendation_user_retrieval_stg"
)

VERTEX_GRAPH_ENDPOINT_NAME: str = os.environ.get("VERTEX_GRAPH_ENDPOINT_NAME", "recommendation_graph_retrieval_stg")

VERTEX_RANKING_ENDPOINT_NAME: str = os.environ.get("VERTEX_RANKING_ENDPOINT_NAME", "recommendation_user_ranking_stg")

VERTEX_PREDICTION_TIMEOUT: float = float(os.environ.get("VERTEX_PREDICTION_TIMEOUT", "10.0" if IS_LOCAL else "2.0"))

# --- 6. Swagger UI for API Testing ---
SWAGGER_UI_EXAMPLE_USER_ID: str = os.environ.get("SWAGGER_UI_EXAMPLE_USER_ID", "")
SWAGGER_UI_EXAMPLE_OFFER_ID: str = os.environ.get("SWAGGER_UI_EXAMPLE_OFFER_ID", "")

# --- 7. Tracking Configuration ---
ENABLE_TRACKING_LOGS: bool = bool(int(os.environ.get("ENABLE_TRACKING_LOGS", "1")))

# --- 8. Redis Configuration ---
REDIS_CACHE_ENABLED: bool = bool(int(os.environ.get("REDIS_CACHE_ENABLED", "0" if IS_LOCAL else "1")))
REDIS_URL: str = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
REDIS_CACHE_RESET_HOUR: int = int(os.environ.get("REDIS_CACHE_RESET_HOUR", "5"))
REDIS_MONITOR_INTERVAL_SECONDS: int = int(os.environ.get("REDIS_MONITOR_INTERVAL_SECONDS", "60"))
REDIS_CA_CERT_PATH: str = os.environ.get("REDIS_CA_CERT_PATH", "")  # Path to PEM file for Redis TLS
REDIS_AUTH_STRING: str = os.environ.get("REDIS_AUTH_STRING", "")  # Optional auth string for Redis

# --- 9. Model Context Configuration ---
SIMILAR_OFFER_MODEL_CONTEXT: str = os.environ.get("SIMILAR_OFFER_MODEL_CONTEXT", "default")
PLAYLIST_RECOMMENDATION_MODEL_CONTEXT: str = os.environ.get("RECO_MODEL_CONTEXT", "default")

# --- 10. Geospatial Configuration ---
GEOSPATIAL_RETRIEVAL_H3_RESOLUTION: int = int(os.environ.get("GEOSPATIAL_RETRIEVAL_H3_RESOLUTION", "5"))

CACHE_H3_RESOLUTION: int = int(os.environ.get("CACHE_H3_RESOLUTION", "8"))

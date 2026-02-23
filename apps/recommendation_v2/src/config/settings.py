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
environment_file_path = Path("../.env")
load_dotenv(dotenv_path=environment_file_path)


# --- 2. Application Environment ---
ENV: str = os.environ.get("ENV", "local")

IS_LOCAL: bool = ENV == "local"
IS_TESTING: bool = ENV == "testing"
IS_STAGING: bool = ENV == "staging"
IS_PROD: bool = ENV == "production"

# Fail-fast mechanism: prevent the app from starting if the environment is unrecognized
if ENV not in ("local", "testing", "staging", "production"):
    raise RuntimeError(f"Unknown environment detected: {ENV}")


# --- 3. Logging Configuration ---
# Reduce log noise in production by defaulting to INFO level
DEBUG_LEVEL: int = logging.INFO if IS_PROD else logging.DEBUG

LOGS_PRETTY_PRINT: bool = bool(int(os.environ.get("LOGS_PRETTY_PRINT", "1")))


# --- 4. Database Configuration (SQL/PostgreSQL) ---
SQL_BASE_DATABASE: str = os.environ.get("SQL_BASE", "")
SQL_BASE_USER: str = os.environ.get("SQL_BASE_USER", "")
SQL_BASE_PASSWORD: str = os.environ.get("SQL_BASE_PASSWORD", "")
SQL_BASE_PORT: str = os.environ.get("SQL_PORT", "5439")
SQL_BASE_HOST: str = os.environ.get("SQL_HOST", "localhost")
SQL_BASE_HOST_SECRET_ID: str = os.environ.get("SQL_HOST_SECRET_ID", "")

# TODO: Fake key for now
API_TOKEN: str = "api_token"

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

VERTEX_RANKING_ENDPOINT_NAME: str = os.environ.get("VERTEX_RANKING_ENDPOINT_NAME", "recommendation_user_ranking_stg")

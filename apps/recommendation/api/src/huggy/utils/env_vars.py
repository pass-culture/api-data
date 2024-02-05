import contextvars
import os

from huggy.utils.secrets import access_secret

# GLOBAL
GCP_PROJECT = os.environ.get("GCP_PROJECT", "passculture-data-ehp")
ENV_SHORT_NAME = os.environ.get("ENV_SHORT_NAME", "dev")
CORS_ALLOWED_ORIGIN = os.environ.get("CORS_ALLOWED_ORIGIN", "*")
API_LOCAL = bool(os.environ.get("API_LOCAL", 0)) == True

# SQL
SQL_BASE_DATABASE = os.environ.get("SQL_BASE", "db")
SQL_BASE_USER = os.environ.get("SQL_BASE_USER", "postgres")
SQL_BASE_PASSWORD = os.environ.get("SQL_BASE_PASSWORD", "postgres")
SQL_BASE_PORT = os.environ.get("SQL_PORT", 5432)
SQL_BASE_HOST = os.environ.get("SQL_HOST", "localhost")
SQL_BASE_HOST_SECRET_ID = os.environ.get("SQL_HOST_SECRET_ID", "")
API_TOKEN = "api_token"

if not API_LOCAL:
    SQL_BASE_SECRET_ID = os.environ.get(
        "SQL_BASE_SECRET_ID",
        "",
    )
    API_TOKEN_SECRET_ID = os.environ.get("API_TOKEN_SECRET_ID")

    try:
        SQL_BASE_PASSWORD = access_secret(GCP_PROJECT, SQL_BASE_SECRET_ID)
        API_TOKEN = access_secret(GCP_PROJECT, API_TOKEN_SECRET_ID)
        SQL_BASE_HOST = access_secret(GCP_PROJECT, SQL_BASE_HOST_SECRET_ID)

    except Exception as e:
        print(e)
        raise Exception("Error on accessing secrets")


# logger
cloud_trace_context = contextvars.ContextVar("cloud_trace_context", default="")
call_id_trace_context = contextvars.ContextVar("call_id_context", default="")
http_request_context = contextvars.ContextVar("http_request_context", default=dict({}))

# config
DEFAULT_SIMILAR_OFFER_MODEL = os.environ.get("DEFAULT_SIMILAR_OFFER_MODEL", "default")
DEFAULT_RECO_MODEL = os.environ.get("DEFAULT_RECO_MODEL", "default")
NUMBER_OF_RECOMMENDATIONS = 40

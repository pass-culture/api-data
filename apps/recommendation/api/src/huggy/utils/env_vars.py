import contextvars
import logging
import os

from huggy.utils.secrets import access_secret


def get_bool_from_env(var_name, default=False):
    """
    Gets a boolean value from an environment variable.
    Accepts 'true', '1', 't', 'y', 'yes', 'on' (case-insensitive) as True.
    """
    value = os.environ.get(var_name)

    if value is None:
        return default

    return value.lower() in {"true", "1", "t", "y", "yes", "on"}


# GLOBAL
GCP_PROJECT = os.environ.get("GCP_PROJECT", "passculture-data-ehp")
ENV_SHORT_NAME = os.environ.get("ENV_SHORT_NAME", "dev")
CORS_ALLOWED_ORIGIN = os.environ.get("CORS_ALLOWED_ORIGIN", "*")
API_LOCAL = get_bool_from_env("API_LOCAL", default=False)
DEBUG_LEVEL = (
    logging.DEBUG
    if get_bool_from_env("DEBUG_LOGS", default=ENV_SHORT_NAME != "prod")
    else logging.INFO
)

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
http_request_context = contextvars.ContextVar("http_request_context", default=None)

# config
SIMILAR_OFFER_MODEL_CONTEXT = os.environ.get("SIMILAR_OFFER_MODEL_CONTEXT", "default")
RECO_MODEL_CONTEXT = os.environ.get("RECO_MODEL_CONTEXT", "default")

DEFAULT_SIMILAR_OFFER_DESCRIPTION = os.environ.get(
    "DEFAULT_SIMILAR_OFFER_DESCRIPTION", "Similar Offer Configuration (default)"
)

DEFAULT_RECO_MODEL_DESCRIPTION = os.environ.get(
    "DEFAULT_RECO_MODEL_DESCRIPTION", "Recommendation Configuration (default)"
)

VERSION_B_RECO_MODEL_DESCRIPTION = os.environ.get(
    "VERSION_B_RECO_MODEL_DESCRIPTION", "Recommendation Configuration (version B)"
)
VERSION_B_SIMILAR_OFFER_DESCRIPTION = os.environ.get(
    "VERSION_B_SIMILAR_OFFER_DESCRIPTION", "Similar Offer Configuration (version B)"
)

VERSION_C_RECO_MODEL_DESCRIPTION = os.environ.get(
    "VERSION_C_RECO_MODEL_DESCRIPTION", "Recommendation Configuration (version C)"
)
VERSION_C_SIMILAR_OFFER_DESCRIPTION = os.environ.get(
    "VERSION_C_SIMILAR_OFFER_DESCRIPTION", "Similar Offer Configuration (version C)"
)


# endpoints
RANKING_VERSION_B_ENDPOINT_NAME = os.environ.get(
    "RANKING_VERSION_B_ENDPOINT_NAME",
    f"recommendation_user_ranking_version_b_{ENV_SHORT_NAME}",
)
NUMBER_OF_RECOMMENDATIONS = int(
    os.environ.get(
        "NUMBER_OF_RECOMMENDATIONS",
        60,
    )
)

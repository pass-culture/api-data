import os

# GCP
ENV_SHORT_NAME = os.environ.get("ENV_SHORT_NAME", "dev")
GCP_LOCATION = os.environ.get("GCP_LOCATION", "europe-west1")

# Mlflow
MLFLOW_TRACKING_TOKEN = os.environ.get("MLFLOW_TRACKING_TOKEN", None)

# API
HASH_ALGORITHM = os.environ.get("VALIDATION_LOGIN_KEY", "HS256")
LOGIN_TOKEN_EXPIRATION = os.environ.get("LOGIN_TOKEN_EXPIRATION", 30)
IS_API_LOCAL = os.environ.get("API_LOCAL", False) == "True"

# Edito
SEARCH_EDITO_MODEL_ENDPOINT_NAME = os.environ.get(
    "SEARCH_EDITO_MODEL_ENDPOINT_NAME",
    f"semantic_search_edito_endpoint_{ENV_SHORT_NAME}",
)

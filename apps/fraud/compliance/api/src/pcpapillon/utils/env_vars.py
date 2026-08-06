import os

# GCP
ENV_SHORT_NAME = os.environ.get("ENV_SHORT_NAME", "dev")
GCP_LOCATION = os.environ.get("GCP_LOCATION", "europe-west1")

IS_API_LOCAL = os.environ.get("API_LOCAL", False) == "True"

# Edito
SEARCH_EDITO_MODEL_ENDPOINT_NAME = os.environ.get(
    "SEARCH_EDITO_MODEL_ENDPOINT_NAME",
    f"semantic_search_edito_endpoint_{ENV_SHORT_NAME}",
)

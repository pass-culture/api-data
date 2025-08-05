import contextvars
import os

from google.cloud import secretmanager


def access_secret(project_id, secret_id):
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{project_id}/secrets/{secret_id}/versions/latest"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")


# Project vars
GCS_BUCKET = os.environ.get("GCS_BUCKET", "data-bucket-dev")
GCP_PROJECT = os.environ.get("GCP_PROJECT", "passculture-data-ehp")
ENV_SHORT_NAME = os.environ.get("ENV_SHORT_NAME", "dev")
SA_ACCOUNT = f"algo-training-{ENV_SHORT_NAME}"

# API_LOCAL is string to match terraform boolean handling
API_LOCAL = os.environ.get("API_LOCAL", False)
IS_API_LOCAL = API_LOCAL == "True"

# API
API_SECRET_KET_SECRET_ID = os.environ.get(
    "API_SECRET_KET_SECRET_ID", "api-papillon-auth-secret-key-dev"
)
# SECRET_KEY = access_secret(GCP_PROJECT, API_SECRET_KET_SECRET_ID)
HASH_ALGORITHM = os.environ.get("VALIDATION_LOGIN_KEY", "HS256")
LOGIN_TOKEN_EXPIRATION = os.environ.get("LOGIN_TOKEN_EXPIRATION", 30)

API_USER_SECRET_ID = os.environ.get("API_USER_SECRET_ID", "api-papillon-user-dev")
API_PWD_SECRET_ID = os.environ.get("API_PWD_SECRET_ID", "api-papillon-password-dev")
# API_USER = access_secret(GCP_PROJECT, API_USER_SECRET_ID)
# API_PWD = access_secret(GCP_PROJECT, API_PWD_SECRET_ID)
# users_db = {
#     API_USER: {
#         "username": API_USER,
#         "password": API_PWD,
#         "disabled": False,
#     }
# }

# logger
cloud_trace_context = contextvars.ContextVar("cloud_trace_context", default="")
call_id_trace_context = contextvars.ContextVar("call_id_context", default="")
http_request_context = contextvars.ContextVar("http_request_context", default={})

# MLFlow
MLFLOW_SECRET_ID = os.environ.get("MLFLOW_SECRET_ID", "mlflow_client_id")
# MLFLOW_CLIENT_ID = access_secret(GCP_PROJECT, MLFLOW_SECRET_ID)
MLFLOW_URL = os.environ.get("MLFLOW_URL", "https://mlflow.staging.passculture.team/")
MLFLOW_TRACKING_TOKEN = os.environ.get("MLFLOW_TRACKING_TOKEN", None)

# Model metadata
MODEL_DEFAULT = os.environ.get("MODEL_DEFAULT", "compliance_model_dev")
MODEL_STAGE = os.environ.get("MODEL_STAGE", "Production")

### LLM Keys
OPENAI_API_KEY = os.environ.get(
    "OPENAI_API_KEY", access_secret(GCP_PROJECT, "openai_api_key")
)

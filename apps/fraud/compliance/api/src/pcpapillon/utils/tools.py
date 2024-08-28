import json
import os

import mlflow
from google.auth.transport.requests import Request
from google.oauth2 import service_account
from pcpapillon.utils.env_vars import (
    GCP_PROJECT,
    MLFLOW_CLIENT_ID,
    MLFLOW_URL,
    SA_ACCOUNT,
    access_secret,
)


def connect_remote_mlflow():
    service_account_dict = json.loads(access_secret(GCP_PROJECT, SA_ACCOUNT))

    id_token_credentials = service_account.IDTokenCredentials.from_service_account_info(
        service_account_dict, target_audience=MLFLOW_CLIENT_ID
    )
    id_token_credentials.refresh(Request())

    os.environ["MLFLOW_TRACKING_TOKEN"] = id_token_credentials.token
    mlflow.set_tracking_uri(MLFLOW_URL)

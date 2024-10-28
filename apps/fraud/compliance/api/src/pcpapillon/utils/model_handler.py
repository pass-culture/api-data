import hashlib
import pickle
from dataclasses import dataclass
from typing import Union

import mlflow
import mlflow.pyfunc
from main import custom_logger
from mlflow import MlflowClient
from pcpapillon.utils.env_vars import (
    ENV_SHORT_NAME,
)
from pcpapillon.utils.tools import connect_remote_mlflow
from sentence_transformers import SentenceTransformer


@dataclass
class ModelWithMetadata:
    model: Union[mlflow.pyfunc.PythonModel, SentenceTransformer]
    model_identifier: str


class ModelHandler:
    MODEL_ALIAS = "@production"

    def __init__(self) -> None:
        custom_logger.info("Connecting to mlflow")
        connect_remote_mlflow()
        self.mlflow_client = MlflowClient()

    def get_model_with_metadata_by_name(
        self,
        model_name: str,
    ) -> ModelWithMetadata:
        mlflow_model_name = self._get_mlflow_model_name(model_name=model_name)

        custom_logger.info(f"Loading model {mlflow_model_name}...")
        loaded_model = mlflow.pyfunc.load_model(
            model_uri=f"models:/{mlflow_model_name}"
        )
        custom_logger.info(f"...Model {mlflow_model_name} loaded")

        model_hash = self.get_model_hash_from_mlflow(model_name=model_name)
        return ModelWithMetadata(
            model=loaded_model,
            model_identifier=model_hash,
        )

    @staticmethod
    def _get_hash(obj):
        return hashlib.md5(pickle.dumps(obj)).hexdigest()

    def get_model_hash_from_mlflow(self, model_name: str):
        mlflow_model_name = self._get_mlflow_model_name(model_name=model_name)
        mlflow_model_name_stripped = mlflow_model_name.removesuffix(
            ModelHandler.MODEL_ALIAS
        )

        custom_logger.info(
            f"Retrieving model version for {mlflow_model_name} registered as {mlflow_model_name_stripped}..."
        )
        model_version = self.mlflow_client.get_latest_versions(
            mlflow_model_name_stripped
        )
        custom_logger.info(f"...Model version retrieved: {model_version}")
        return self._get_hash(model_version)

    @staticmethod
    def _get_mlflow_model_name(model_name: str):
        return f"api_{model_name}_{ENV_SHORT_NAME}{ModelHandler.MODEL_ALIAS}"

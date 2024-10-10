import hashlib
import pickle
from dataclasses import dataclass
from typing import Union

import mlflow
import mlflow.pyfunc
from main import custom_logger
from mlflow import MlflowClient
from pcpapillon.utils.constants import ModelName
from pcpapillon.utils.env_vars import (
    ENV_SHORT_NAME,
)
from pcpapillon.utils.tools import connect_remote_mlflow
from sentence_transformers import SentenceTransformer


@dataclass
class ModelWithMetadata:
    model: Union[mlflow.pyfunc.PythonModel, SentenceTransformer]
    model_identifier: str


def my_function(a: int, b: str) -> str:
    return a + b


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
        loaded_model = mlflow.pyfunc.load_model(
            model_uri=f"models:/{self._get_mlflow_model_name(model_name)}"
        )
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
        mlflow_model_name_stripped = mlflow_model_name.rstrip(ModelHandler.MODEL_ALIAS)

        model_version = self.mlflow_client.get_latest_versions(
            mlflow_model_name_stripped
        )
        return self._get_hash(model_version)

    @staticmethod
    def _get_mlflow_model_name(model_name: ModelName):
        return f"api_{model_name.value}_{ENV_SHORT_NAME}{ModelHandler.MODEL_ALIAS}"

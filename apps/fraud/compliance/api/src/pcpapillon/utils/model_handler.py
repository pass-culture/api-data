import hashlib
import pickle
import re
from dataclasses import dataclass
from typing import Union

import mlflow
import mlflow.pyfunc
from main import custom_logger
from mlflow import MlflowClient
from pcpapillon.utils.constants import ModelName, ModelType
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
    def __init__(self) -> None:
        custom_logger.info("Connecting to mlflow")
        connect_remote_mlflow()
        self.mlflow_client = MlflowClient()

    def get_model_with_metadata_by_name(
        self, model_name: str, model_type=ModelType.DEFAULT
    ) -> ModelWithMetadata:
        if model_name == ModelName.COMPLIANCE:
            loaded_model = mlflow.pyfunc.load_model(
                model_uri=f"models:/{self._get_mlflow_model_name(model_name)}"
            )
            model_hash = self.get_model_hash_from_mlflow(model_name=model_name)

        elif model_name == ModelName.OFFER_CATEGORISATION:
            loaded_model = mlflow.catboost.load_model(
                model_uri=f"models:/{self._get_mlflow_model_name(model_name)}"
            )
            model_hash = self.get_model_hash_from_mlflow(model_name=model_name)
        else:
            if model_type == ModelType.PREPROCESSING:
                loaded_model = SentenceTransformer(model_name, device="cpu")
                model_hash = f"hash_preproc_{model_name}"
            else:
                raise ValueError(
                    f"Model name {model_name} not found with type {model_type}"
                )
        return ModelWithMetadata(
            model=loaded_model,
            model_identifier=model_hash,
        )

    @staticmethod
    def _get_hash(obj):
        obj_bytes = pickle.dumps(obj)
        return hashlib.md5(obj_bytes).hexdigest()

    def get_model_hash_from_mlflow(self, model_name: str):
        SPLIT_PATTERN = "/|@"

        mlflow_model_name = self._get_mlflow_model_name(model_name=model_name)
        mlflow_model_name_stripped = re.split(SPLIT_PATTERN, mlflow_model_name)[0]

        model_version = self.mlflow_client.get_latest_versions(
            mlflow_model_name_stripped
        )
        return self._get_hash(model_version)

    @staticmethod
    def _get_mlflow_model_name(model_name: ModelName):
        if model_name == ModelName.COMPLIANCE:
            return f"api_{model_name.value}_default_{ENV_SHORT_NAME}@production"
        elif model_name == ModelName.OFFER_CATEGORISATION:
            return f"{model_name.value}_{ENV_SHORT_NAME}/production"

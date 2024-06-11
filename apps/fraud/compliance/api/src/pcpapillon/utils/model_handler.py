import hashlib
import pickle
from dataclasses import dataclass
from typing import Union

import mlflow
import mlflow.pyfunc
from catboost import CatBoostClassifier
from main import custom_logger
from mlflow import MlflowClient
from pcpapillon.utils.env_vars import (
    ENV_SHORT_NAME,
    MLFLOW_CLIENT_ID,
    isAPI_LOCAL,
)
from pcpapillon.utils.tools import connect_remote_mlflow
from sentence_transformers import SentenceTransformer


@dataclass
class ModelWithMetadata:
    model: Union[mlflow.pyfunc.PythonModel, SentenceTransformer]
    model_identifier: str


class ModelHandler:
    COMPLICANCE_LOCAL_PATH = "pcpapillon/local_model/model.cb"
    OFFER_RECOMMENDATION_LOCAL_PATH = (
        "pcpapillon/local_model/offer_categorisation_model.cb"
    )

    def __init__(self) -> None:
        if not isAPI_LOCAL:
            custom_logger.info("Connecting to mlflow")
            connect_remote_mlflow(MLFLOW_CLIENT_ID)
            self.mlflow_client = MlflowClient()
        else:
            custom_logger.info("Local API, no mlflow client")
            self.mlflow_client = None

    def get_model_with_metadata_by_name(
        self, model_name, model_type="default"
    ) -> ModelWithMetadata:
        if model_type == "default":
            mlflow_model_name = self._get_mlflow_model_name(model_name)
            loaded_model = mlflow.catboost.load_model(
                model_uri=f"models:/{mlflow_model_name}"
            )
            model_hash = self.get_model_hash_from_mlflow(model_name=model_name)
            return ModelWithMetadata(model=loaded_model, model_identifier=model_hash)
        elif model_type == "local":
            # We do not factorize below because we want local models to be defined generically
            if model_name == "compliance":
                model = CatBoostClassifier(one_hot_max_size=65)
                loaded_model = model.load_model(self.COMPLICANCE_LOCAL_PATH)
                model_hash = self._get_hash(obj=loaded_model)
            elif model_name == "offer_categorisation":
                model = CatBoostClassifier(one_hot_max_size=65)
                loaded_model = model.load_model(self.OFFER_RECOMMENDATION_LOCAL_PATH)
                model_hash = self._get_hash(obj=loaded_model)
            else:
                raise ValueError(
                    f"Model {model_name} with type 'local' not found. name should be one of ['compliance', 'offer_categorisation']"
                )
            return ModelWithMetadata(model=loaded_model, model_identifier=model_hash)
        elif model_type == "custom_sentence_transformer":
            return ModelWithMetadata(
                model=SentenceTransformer(model_name),
                model_identifier=model_name,
            )

        raise ValueError(
            f"Model type {model_type} not found. type should be one of ['default', 'local', 'custom_sentence_transformer']"
        )

    @staticmethod
    def _get_hash(obj):
        obj_bytes = pickle.dumps(obj)
        return hashlib.md5(obj_bytes).hexdigest()

    def get_model_hash_from_mlflow(self, model_name: str):
        mlflow_model_name = self._get_mlflow_model_name(model_name=model_name)
        if not self.mlflow_client:
            raise ValueError("No mlflow client connected")

        model_version = self.mlflow_client.get_latest_versions(
            mlflow_model_name, stages=["Production"]
        )

        return self._get_hash(model_version)

    @staticmethod
    def _get_mlflow_model_name(model_name: str):
        if model_name == "compliance":
            return f"{model_name}_default_{ENV_SHORT_NAME}/Production"
        elif model_name == "offer_categorisation":
            return f"{model_name}_{ENV_SHORT_NAME}/Production"
        raise ValueError(
            "Only compliance and offer_categorisation are registered in mlflow"
        )

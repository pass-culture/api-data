import threading
from typing import Union

import mlflow
from main import custom_logger
from pcpapillon.core.compliance.predict import get_prediction_and_main_contribution
from pcpapillon.core.compliance.preprocess import preprocess
from pcpapillon.utils.config_handler import ConfigHandler
from pcpapillon.utils.constants import APIType, ConfigName, ModelName, ModelType
from pcpapillon.utils.data_model import APIConfig, ModelConfig
from pcpapillon.utils.env_vars import (
    IS_API_LOCAL,
)
from pcpapillon.utils.model_handler import ModelHandler
from sentence_transformers import SentenceTransformer


class ComplianceModel:
    MODEL_NAME = ModelName.COMPLIANCE
    MODEL_TYPE = ModelType.LOCAL if IS_API_LOCAL else ModelType.DEFAULT
    PREPROC_MODEL_TYPE = MODEL_TYPE.PREPROCESSING

    def __init__(self):
        self.model_handler = ModelHandler()
        self.api_config, self.model_config = self._load_config()
        self.classfier_model, self.classifier_model_identifier, self.prepoc_models = (
            self._load_models()
        )
        self.classfier_model_lock: threading.Lock = threading.Lock()

    @staticmethod
    def _load_config() -> tuple[APIConfig, ModelConfig]:
        api_config = ConfigHandler.get_config_by_name_and_type(
            ConfigName.API, APIType.DEFAULT
        )
        model_config = ConfigHandler.get_config_by_name_and_type(
            ConfigName.MODEL, ModelType.DEFAULT
        )
        return api_config, model_config

    def _load_models(
        self,
    ) -> tuple[
        Union[mlflow.pyfunc.PythonModel, SentenceTransformer],
        str,
        dict[str, SentenceTransformer],
    ]:
        custom_logger.info("load classification model..")
        catboost_model_with_metadata = (
            self.model_handler.get_model_with_metadata_by_name(
                model_name=self.MODEL_NAME, model_type=self.MODEL_TYPE
            )
        )

        custom_logger.info("load preprocessings model..")
        prepoc_models = {}
        for (
            feature_type,
            sentence_transformer_name,
        ) in self.model_config.pre_trained_model_for_embedding_extraction.items():
            prepoc_models[feature_type] = (
                self.model_handler.get_model_with_metadata_by_name(
                    model_name=sentence_transformer_name,
                    model_type=self.PREPROC_MODEL_TYPE,
                ).model
            )

        custom_logger.info(
            f"Preprocessing models for {self.MODEL_NAME} : {prepoc_models}"
        )
        return (
            catboost_model_with_metadata.model,
            catboost_model_with_metadata.model_identifier,
            prepoc_models,
        )

    def predict(self, data):
        """
        Predicts the class labels for the given data using the trained classifier model.

        Args:
            api_config (dict): Configuration parameters for the API.
            model_config (dict): Configuration parameters for the model.
            data (list): Input data to be predicted.

        Returns:
            tuple: A tuple containing the predicted class labels and the main contribution.
                offer validition probability
                offer rejection probability (=1-proba_val)
                main features contributing to increase validation probability
                main features contributing to reduce validation probability
        """

        # Preprocess the data and the embedder
        pool, data_w_emb = preprocess(
            self.api_config, self.model_config, data, self.prepoc_models
        )

        # Run the prediction
        return get_prediction_and_main_contribution(
            self.classfier_model, data_w_emb, pool
        )

    def _is_newer_model_available(self) -> bool:
        return (
            self.classifier_model_identifier
            != self.model_handler.get_model_hash_from_mlflow(self.MODEL_NAME)
        )

    def reload_model_if_newer_is_available(self):
        custom_logger.info("Checking if newer model is available...")
        # To prevent simultaneous model reloads : the following block is thread-safe.
        # e.g. it won't be exectued by multiple threads at the same time
        with self.classfier_model_lock:
            if self._is_newer_model_available():
                classfier_model_with_metadata = (
                    self.model_handler.get_model_with_metadata_by_name(
                        model_name=self.MODEL_NAME, model_type=self.MODEL_TYPE
                    )
                )
                self.classfier_model, self.classifier_model_identifier = (
                    classfier_model_with_metadata.model,
                    classfier_model_with_metadata.model_identifier,
                )
                custom_logger.info(
                    f"...New model loaded with hash {self.classifier_model_identifier}"
                )
            else:
                custom_logger.info("...No newer model available")

import hashlib
import pickle
from typing import Any

from main import custom_logger
from pcpapillon.core.compliance.predict import get_prediction_and_main_contribution
from pcpapillon.core.compliance.preprocess import preprocess
from pcpapillon.utils.config_handler import ConfigHandler
from pcpapillon.utils.data_model import APIConfig, ModelConfig, ModelParams
from pcpapillon.utils.env_vars import (
    isAPI_LOCAL,
)
from pcpapillon.utils.model_handler import ModelHandler


class ComplianceModel:
    def __init__(self, api_config, model_config):
        self.api_config = api_config
        self.model_config = model_config
        self.classfier_model, self.prepoc_models = self._load_models(
            model_config=self.model_config
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

    @staticmethod
    def _load_models(model_config: ModelConfig) -> tuple[Any, dict[str, Any]]:
        custom_logger.info("load_compliance_model..")
        loaded_model = ModelHandler.get_model_by_name(
            name="compliance", type="local" if isAPI_LOCAL else "default"
        )

        custom_logger.info("load_preproc_model..")
        prepoc_models = {}
        for (
            feature_type,
            sentence_transformer_name,
        ) in model_config.pre_trained_model_for_embedding_extraction.items():
            prepoc_models[feature_type] = ModelHandler.get_model_by_name(
                name=sentence_transformer_name, type="custom_sentence_transformer"
            )

        custom_logger.info("Preprocessing models for compliance : {prepoc_models}")

        return loaded_model, prepoc_models

    def _load_config() -> tuple[APIConfig, ModelConfig]:
        config_handler = ConfigHandler()
        api_config = config_handler.get_config_by_name_and_type("API", "default")
        model_config = config_handler.get_config_by_name_and_type("model", "default")
        return api_config, model_config

    def reload_classification_model(self, model_params: ModelParams) -> None:
        self.classfier_model = ModelHandler().get_model_by_name(
            model_params.name, model_params.type
        )
        self.model_config = ConfigHandler().get_config_by_name_and_type(
            "model", model_params.type
        )

    def _check_is_model_available(self) -> bool:
        def get_object_hash(obj):
            # Serialize the object to a byte stream
            obj_bytes = pickle.dumps(obj)

            # Compute the hash of the serialized data
            obj_hash = hashlib.md5(obj_bytes).hexdigest()

            return obj_hash

        return get_object_hash(self.classfier_model)

    async def reload_model_if_newer_is_available(self):
        custom_logger.info("Checking if newer model is available...")
        custom_logger.info(self._check_is_model_available())

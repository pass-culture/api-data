from typing import Any

from main import custom_logger
from pcpapillon.utils.config_handler import ConfigHandler
from pcpapillon.utils.data_model import APIConfig, ModelConfig
from pcpapillon.utils.env_vars import (
    isAPI_LOCAL,
)
from pcpapillon.utils.model_handler import ModelHandler


def load_models(model_config: ModelConfig) -> tuple[Any, dict[str, Any]]:
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
    return loaded_model, prepoc_models


def load_config() -> tuple[APIConfig, ModelConfig]:
    config_handler = ConfigHandler()
    api_config = config_handler.get_config_by_name_and_type("API", "default")
    model_config = config_handler.get_config_by_name_and_type("model", "default")
    return api_config, model_config

from main import custom_logger
from pcpapillon.utils.config_handler import ConfigHandler
from pcpapillon.utils.env_vars import (
    isAPI_LOCAL,
)
from pcpapillon.utils.model_handler import ModelHandler


def load_models(model_config):
    model_handler = ModelHandler(model_config)

    custom_logger.info("load_compliance_model..")
    model_loaded = model_handler.get_model_by_name(
        name="compliance", type="local" if isAPI_LOCAL else "default"
    )
    custom_logger.info("load_preproc_model..")
    prepoc_models = {}
    for feature_type in model_config.pre_trained_model_for_embedding_extraction.keys():
        prepoc_models[feature_type] = model_handler.get_model_by_name(feature_type)
    return model_loaded, prepoc_models


def load_config():
    config_handler = ConfigHandler()
    api_config = config_handler.get_config_by_name_and_type("API", "default")
    model_config = config_handler.get_config_by_name_and_type("model", "default")
    return api_config, model_config

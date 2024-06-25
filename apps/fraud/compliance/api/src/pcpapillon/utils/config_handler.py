from pcpapillon.utils.configs import configs
from pcpapillon.utils.constants import ConfigName
from pcpapillon.utils.data_model import APIConfig, ModelConfig


class ConfigHandler:
    @staticmethod
    def get_api_config(config_type):
        return APIConfig.from_dict(configs[ConfigName.API][config_type])

    def get_model_config(config_type):
        return ModelConfig.from_dict(configs[ConfigName.MODEL][config_type])

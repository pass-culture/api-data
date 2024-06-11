from pcpapillon.utils.configs import configs
from pcpapillon.utils.data_model import APIConfig, ModelConfig


class ConfigHandler:
    @staticmethod
    def get_config_by_name_and_type(name, config_type):
        if name == "API":
            return APIConfig.from_dict(configs[name][config_type])
        if name == "model":
            return ModelConfig.from_dict(configs[name][config_type])
        return

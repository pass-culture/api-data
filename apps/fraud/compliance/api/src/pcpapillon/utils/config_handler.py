from pcpapillon.utils.configs import configs
from pcpapillon.utils.constants import ConfigName
from pcpapillon.utils.data_model import APIConfig, ModelConfig


class ConfigHandler:
    @staticmethod
    def get_config_by_name_and_type(name, config_type):
        if name is ConfigName.API:
            return APIConfig.from_dict(configs[name][config_type])
        if name is ConfigName.MODEL:
            return ModelConfig.from_dict(configs[name][config_type])
        raise ValueError(
            f"Config name {name} not found. name should be one of {ConfigName.__members__}"
        )

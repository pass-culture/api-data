from pcpapillon.utils.model_handler import ModelHandler
from pcpapillon.utils.config_handler import ConfigHandler

config_handler = ConfigHandler()
api_config = config_handler.get_config_by_name_and_type("API", "default")
model_config_default = config_handler.get_config_by_name_and_type("model", "default")
model_handler_default = ModelHandler(model_config_default)

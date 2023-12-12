import logging
from huggy.utils.cloud_logging.filter import GoogleCloudLogFilter
from huggy.utils.cloud_logging.logger import CustomLogger
from huggy.utils.env_vars import API_LOCAL


def setup_logging():
    if API_LOCAL == True:
        logger = logging.getLogger("uvicorn")
        logger.warning("This API is running in LOCAL MODE")
        return logger
    else:
        from google.cloud.logging import Client
        from fastapi.logger import logger

        client = Client()
        handler = client.get_default_handler()
        handler.setLevel(logging.DEBUG)
        handler.filters = []
        handler.addFilter(GoogleCloudLogFilter(project=client.project))
        logger.handlers = []
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        return CustomLogger()

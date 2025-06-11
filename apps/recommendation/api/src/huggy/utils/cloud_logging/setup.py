import logging

from huggy.utils.cloud_logging.filter import GoogleCloudLogFilter
from huggy.utils.cloud_logging.logger import CustomLogger
from huggy.utils.env_vars import API_LOCAL, DEBUG_LEVEL


def setup_logging():
    if API_LOCAL is True:
        logger = logging.getLogger("uvicorn")
        logger.warning("This API is running in LOCAL MODE")
        return logger
    else:
        from fastapi.logger import logger
        from google.cloud.logging import Client

        client = Client()
        handler = client.get_default_handler()
        handler.setLevel(DEBUG_LEVEL)
        handler.filters = []
        handler.addFilter(GoogleCloudLogFilter(project=client.project))
        logger.handlers = []
        logger.addHandler(handler)
        logger.setLevel(DEBUG_LEVEL)
        return CustomLogger()

import logging

import google.cloud.logging
from fastapi.logger import logger

from huggy.utils.cloud_logging.filter import GoogleCloudLogFilter
from huggy.utils.cloud_logging.logger import CustomLogger
from huggy.utils.env_vars import API_LOCAL


def setup_logging():
    try:
        if API_LOCAL == True:
            return logging.getLogger("uvicorn")
        else:
            client = google.cloud.logging.Client()
            handler = client.get_default_handler()
            handler.setLevel(logging.DEBUG)
            handler.filters = []
            handler.addFilter(GoogleCloudLogFilter(project=client.project))
            logger.handlers = []
            logger.addHandler(handler)
            logger.setLevel(logging.DEBUG)
            return CustomLogger()
    except:
        return logging.getLogger("uvicorn")

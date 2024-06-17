import logging

import google.cloud.logging
from fastapi.logger import logger
from pcpapillon.utils.cloud_logging.custom_logger import CustomLogger
from pcpapillon.utils.cloud_logging.google_cloud_log_filter import GoogleCloudLogFilter
from pcpapillon.utils.env_vars import IS_API_LOCAL


def setup_logging():
    if IS_API_LOCAL:
        api_logger = logging.getLogger("uvicorn")
    else:
        client = google.cloud.logging.Client()
        handler = client.get_default_handler()
        handler.setLevel(logging.DEBUG)
        handler.filters = []
        handler.addFilter(GoogleCloudLogFilter(project=client.project))
        logger.handlers = []
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        api_logger = CustomLogger()
    return api_logger

import logging

import google.cloud.logging
from fastapi.logger import logger as fastapi_logger
from pcpapillon.utils.env_vars import IS_API_LOCAL
from pcpapillon.utils.logging.custom_logger import CustomLogger
from pcpapillon.utils.logging.google_cloud_log_filter import GoogleCloudLogFilter


def setup_logging():
    if IS_API_LOCAL:
        api_logger = logging.getLogger("uvicorn")
        api_logger.setLevel(logging.DEBUG)
    else:
        client = google.cloud.logging.Client()
        handler = client.get_default_handler()
        handler.setLevel(logging.DEBUG)
        handler.filters = []
        handler.addFilter(GoogleCloudLogFilter(project=client.project))
        api_logger = fastapi_logger
        api_logger.handlers = []
        api_logger.addHandler(handler)
        api_logger.setLevel(logging.DEBUG)

    return CustomLogger(logger=api_logger)

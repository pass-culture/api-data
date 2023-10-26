import logging
from huggy.utils.cloud_logging.filter import GoogleCloudLogFilter
from huggy.utils.cloud_logging.logger import CustomLogger
from huggy.utils.env_vars import API_LOCAL


def setup_logging():
    try:
        if API_LOCAL == True:
            logger = logging.getLogger("uvicorn")
            logger.warn("This API is running in LOCAL MODE")
            return logger
        else:
            import google.cloud.logging

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
        logger = logging.getLogger("uvicorn")
        return logger

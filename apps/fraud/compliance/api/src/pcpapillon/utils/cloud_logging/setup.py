import logging

from fastapi import Request
from fastapi.logger import logger
from fastapi.logger import logger as fastapi_logger
from google.cloud import logging as gcloud_logging
from pcpapillon.utils.cloud_logging.filter import GoogleCloudLogFilter
from pcpapillon.utils.env_vars import (
    cloud_trace_context,
    isAPI_LOCAL,
)


class CustomLogger:
    def info(self, message=None, extra=None):
        log_entry = {
            "message": message,
            "extra": extra,
        }
        fastapi_logger.info(log_entry)
        return


def setup_logging():
    # Clear existing handlers
    fastapi_logger.handlers = []

    if isAPI_LOCAL:
        # Local development with Uvicorn or Gunicorn with Uvicorn workers
        # uvicorn_logger = logging.getLogger("uvicorn")
        # uvicorn_logger.setLevel(logging.DEBUG)
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(levelname)s: %(asctime)s - %(message)s")
        )
        # uvicorn_logger.addHandler(handler)
        fastapi_logger.addHandler(handler)
        fastapi_logger.setLevel(logging.DEBUG)
        api_logger = fastapi_logger
    else:
        # Production on Cloud Run
        client = gcloud_logging.Client()
        handler = client.get_default_handler()
        handler.setLevel(logging.DEBUG)
        handler.filters = []
        handler.addFilter(GoogleCloudLogFilter(project=client.project))
        logger.handlers = []
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        api_logger = CustomLogger()
    return api_logger


async def setup_trace(request: Request):
    if "x-cloud-trace-context" in request.headers:
        cloud_trace_context.set(request.headers.get("x-cloud-trace-context"))

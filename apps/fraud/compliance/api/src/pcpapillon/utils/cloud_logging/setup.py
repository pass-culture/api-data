import logging

from fastapi import Request
from fastapi.logger import logger as fastapi_logger
from google.cloud import logging as gcloud_logging
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
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(levelname)s: %(asctime)s - %(message)s")
        )
        fastapi_logger.addHandler(handler)
        fastapi_logger.setLevel(logging.DEBUG)
        api_logger = fastapi_logger
    else:
        # Production on Cloud Run
        client = gcloud_logging.Client()
        gcloud_handler = client.get_default_handler()
        gcloud_handler.setLevel(logging.DEBUG)
        gcloud_handler.setFormatter(
            logging.Formatter("%(levelname)s: %(asctime)s - %(message)s")
        )

        # Gunicorn/Console logging
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)
        console_handler.setFormatter(
            logging.Formatter("%(levelname)s: %(asctime)s - %(message)s")
        )

        fastapi_logger.addHandler(gcloud_handler)
        fastapi_logger.addHandler(console_handler)
        fastapi_logger.setLevel(logging.DEBUG)
        api_logger = CustomLogger()
    return api_logger


async def setup_trace(request: Request):
    if "x-cloud-trace-context" in request.headers:
        cloud_trace_context.set(request.headers.get("x-cloud-trace-context"))

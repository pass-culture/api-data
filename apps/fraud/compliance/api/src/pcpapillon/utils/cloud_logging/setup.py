import logging

from fastapi import Request
from fastapi.logger import logger as fastapi_logger
from google.cloud import logging as gcloud_logging
from pcpapillon.utils.cloud_logging.custom_logger import (
    CustomLogger,
)
from pcpapillon.utils.cloud_logging.google_cloud_log_filter import (
    GoogleCloudLogFilter,
)
from pcpapillon.utils.env_vars import (
    cloud_trace_context,
    isAPI_LOCAL,
)


def setup_logging():
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(
        logging.Formatter("%(levelname)s: %(asctime)s - %(message)s")
    )

    # Clear existing handlers
    fastapi_logger.handlers = []
    fastapi_logger.addHandler(console_handler)
    fastapi_logger.setLevel(logging.DEBUG)

    if not isAPI_LOCAL:
        # Production on Cloud Run
        client = gcloud_logging.Client()
        gcloud_handler = client.get_default_handler()
        gcloud_handler.setLevel(logging.DEBUG)
        gcloud_handler.setFormatter(
            logging.Formatter("%(levelname)s: %(asctime)s - %(message)s")
        )
        gcloud_handler.filters = []
        gcloud_handler.addFilter(GoogleCloudLogFilter(project=client.project))

        fastapi_logger.addHandler(console_handler)
    return CustomLogger()


async def setup_trace(request: Request):
    if "x-cloud-trace-context" in request.headers:
        cloud_trace_context.set(request.headers.get("x-cloud-trace-context"))

import contextvars
import json
import logging
import sys
from typing import Any

from google.cloud import logging as google_logging
from google.cloud.logging_v2.handlers import CloudLoggingFilter

from config import settings


# --- Context Variables for Async Request Tracking ---
# In an asynchronous framework like FastAPI, multiple requests run concurrently in the same process.
# Global variables would bleed data between requests. `contextvars` ensures that these
# variables are strictly isolated to the current asynchronous execution context (the current HTTP request).
call_id_context: contextvars.ContextVar[str] = contextvars.ContextVar("call_id_context", default="unknown")
cloud_trace_context: contextvars.ContextVar[str] = contextvars.ContextVar("cloud_trace_context", default="")
http_request_context: contextvars.ContextVar[dict[str, Any] | None] = contextvars.ContextVar("http_request_context")


class StructuredLogger:
    """
    A wrapper around the standard Python logger to enforce structured logging.

    This ensures every log entry is consistently formatted either as a JSON string
    (for local development readability) or as a dictionary payload (which Google Cloud
    Logging automatically parses into `jsonPayload`). It automatically injects the
    `call_id` from the current async context.
    """

    def __init__(self, base_logger: logging.Logger):
        self._logger = base_logger

    def _format_log(self, message: str, extra: dict | None) -> Any:
        """
        Formats the final log payload before passing it to the underlying handler.
        """
        payload = {"message": message, "extra": extra, "call_id": call_id_context.get()}

        # Pretty print for local debugging if configured
        if settings.IS_LOCAL and settings.LOGS_PRETTY_PRINT:
            return "\n" + json.dumps(payload, indent=2, default=str, ensure_ascii=False)

        # In production (GCP), returning a dict allows the Google handler to structure it natively
        return payload

    def info(self, message: Any, extra: dict | None = None) -> None:
        self._logger.info(self._format_log(str(message), extra))

    def warning(self, message: Any, extra: dict | None = None) -> None:
        self._logger.warning(self._format_log(str(message), extra))

    def error(self, message: Any, extra: dict | None = None) -> None:
        self._logger.error(self._format_log(str(message), extra))

    def debug(self, message: Any, extra: dict | None = None) -> None:
        self._logger.debug(self._format_log(str(message), extra))


class GoogleCloudLogFilter(CloudLoggingFilter):
    """
    A custom log filter that intercepts log records before they are sent to GCP.

    It extracts the HTTP request details and the GCP Trace ID from the current
    asynchronous context and injects them into the log record. This enables
    GCP Log Explorer to group all logs belonging to the same HTTP request
    under a single expandable trace entry.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        # Inject HTTP request metadata (URL, method, user-agent, etc.)
        record.http_request = http_request_context.get(None) or {}

        # Inject GCP Trace ID for cross-service observability
        trace_id = cloud_trace_context.get()
        if trace_id:
            # The header is usually in the format "TRACE_ID/SPAN_ID;o=TRACE_TRUE"
            split_header = trace_id.split("/", 1)
            clean_trace_id = split_header[0]
            record.trace = f"projects/{self.project}/traces/{clean_trace_id}"

        return super().filter(record)


def initialize_application_logger() -> StructuredLogger:
    """
    Configures and initializes the application logger based on the running environment.

    This function distinguishes between two operational modes:
    1. Local Development:
       - Attaches to the 'uvicorn.error' logger to align with the server's logging system.
       - Outputs logs to standard output (stdout) through Uvicorn's existing handlers.
       - Applies the configured debug level to ensure visibility of application logs.

    2. Cloud Environment (GCP):
       - Integrates with Google Cloud Logging.
       - Injects trace IDs for distributed tracing across microservices.
       - Uses the root logger to capture all application logs.

    Returns:
        StructuredLogger: An instance of the custom logger wrapper ready for use.
    """
    if settings.IS_LOCAL:
        logger_name = "uvicorn.error"
        local_logger = logging.getLogger(logger_name)

        # Set the logging level based on configuration (DEBUG, INFO, etc.)
        local_logger.setLevel(settings.LOG_LEVEL)

        # Ensure we have at least one handler to see output in the console
        if not local_logger.handlers:
            console_handler = logging.StreamHandler(sys.stdout)
            local_logger.addHandler(console_handler)

        return StructuredLogger(local_logger)

    else:
        # Initialize Google Cloud Logging client
        gcp_logging_client = google_logging.Client(project=settings.GCP_PROJECT)

        # Retrieve the default handler which automatically formats logs for GCP
        gcp_log_handler = gcp_logging_client.get_default_handler()
        gcp_log_handler.setLevel(settings.LOG_LEVEL)

        # Attach the custom filter to inject trace context (Trace ID, Span ID)
        trace_context_filter = GoogleCloudLogFilter(project=gcp_logging_client.project)
        gcp_log_handler.addFilter(trace_context_filter)

        # Configure the root logger to capture all logs in the container environment
        root_logger = logging.getLogger()
        root_logger.setLevel(settings.LOG_LEVEL)

        # Replace existing handlers to ensure only the GCP handler is used
        root_logger.handlers = [gcp_log_handler]

        return StructuredLogger(root_logger)


# Initialize the global logger instance to be imported across the application
logger = initialize_application_logger()

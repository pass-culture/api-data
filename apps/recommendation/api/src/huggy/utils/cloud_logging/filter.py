import logging

from google.cloud.logging_v2.handlers import CloudLoggingFilter
from huggy.utils.env_vars import (
    cloud_trace_context,
    http_request_context,
)


class GoogleCloudLogFilter(CloudLoggingFilter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.http_request = http_request_context.get() or {}

        trace = cloud_trace_context.get()
        split_header = trace.split("/", 1)

        record.trace = f"projects/{self.project}/traces/{split_header[0]}"

        super().filter(record)

        return True

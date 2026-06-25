"""
GCP Trace & HTTP-Request Context Middleware.

For every incoming request this middleware:
  1. Reads the ``X-Cloud-Trace-Context`` header and stores it in
     ``cloud_trace_context`` so that :class:`~services.logger.GoogleCloudLogFilter`
     can attach it to every log record emitted during the request.
  2. Builds a ``httpRequest`` dict (matching the structure expected by the
     Google Cloud Logging API) and stores it in ``http_request_context``.

``call_id_context`` is intentionally **not** set here: each pipeline controller
already assigns its own business-scoped UUID (the one returned to the client and
used for tracking), so letting the middleware override it would create a mismatch
between logged call-ids and the ids stored in the data warehouse.

Header format (Cloud Run / Cloud Load Balancer):
    X-Cloud-Trace-Context: TRACE_ID/SPAN_ID;o=TRACE_TRUE
"""

from collections.abc import Awaitable
from collections.abc import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from services.logger import cloud_trace_context
from services.logger import http_request_context


# Header injected by Google Cloud infrastructure (Cloud Run)
_TRACE_HEADER = "x-cloud-trace-context"


class GCPTraceMiddleware(BaseHTTPMiddleware):
    """
    ASGI middleware that populates GCP-related :mod:`contextvars` for the
    duration of each HTTP request.

    It must be added **before** any business-logic middleware so that all
    subsequent log calls already carry the enriched context.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        # ---------------------------------------------------------------------------
        # Cloud Trace context
        # ---------------------------------------------------------------------------
        raw_trace_header = request.headers.get(_TRACE_HEADER, "")
        token_trace = cloud_trace_context.set(raw_trace_header)

        # ---------------------------------------------------------------------------
        # HTTP Request context
        # ---------------------------------------------------------------------------
        http_request_payload: dict[str, str] = {
            "requestMethod": request.method,
            "requestUrl": str(request.url),
            "userAgent": request.headers.get("user-agent", ""),
            "remoteIp": request.client.host if request.client else "",
            "protocol": f"HTTP/{request.scope.get('http_version', '1.1')}",
            "requestSize": request.headers.get("content-length", "0"),
        }
        token_http = http_request_context.set(http_request_payload)

        try:
            response = await call_next(request)
        finally:
            cloud_trace_context.reset(token_trace)
            http_request_context.reset(token_http)

        return response

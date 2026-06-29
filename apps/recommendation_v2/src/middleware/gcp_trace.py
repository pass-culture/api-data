from starlette.requests import Request
from starlette.types import ASGIApp
from starlette.types import Receive
from starlette.types import Scope
from starlette.types import Send

from services.logger import cloud_trace_context
from services.logger import http_request_context


# Header injected by Google Cloud infrastructure (Cloud Run)
_TRACE_HEADER = "x-cloud-trace-context"


class GCPTraceMiddleware:
    """
    Pure ASGI middleware populating GCP-related contextvars.
    No Task boundaries, compatible with contextvars, StreamingResponses, and BackgroundTasks.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope)

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
            "protocol": f"HTTP/{scope.get('http_version', '1.1')}",
            "requestSize": request.headers.get("content-length", "0"),
        }
        token_http = http_request_context.set(http_request_payload)

        try:
            await self.app(scope, receive, send)
        finally:
            cloud_trace_context.reset(token_trace)
            http_request_context.reset(token_http)

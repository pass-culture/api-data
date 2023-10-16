from traceback import print_exception

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from huggy.utils.cloud_logging import logger
import traceback


class ExceptionHandlerMiddleware(BaseHTTPMiddleware):
    def dispatch(self, request: Request, call_next):
        try:
            return call_next(request)
        except Exception as e:
            print_exception(e)
            tb = traceback.format_exc()
            logger.error(
                "Exception error",
                extra={
                    "details": {
                        "content": {
                            "error": e.__class__.__name__,
                            "messages": e.args,
                            "trace": tb,
                        }
                    }
                },
            )
            return JSONResponse(status_code=500, content={"error": "Client Error"})

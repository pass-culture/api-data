import traceback
import anyio
from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse

from huggy.utils.cloud_logging import logger


def log_error(exc: Exception, message: str):
    tb = traceback.format_exc()
    logger.error(
        message,
        extra={
            "details": {
                "content": {
                    "error": exc.__class__.__name__,
                    "trace": tb,
                }
            }
        },
    )


class NotAuthorized(Exception):
    pass


class ExceptionHandlerMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)
        except NotAuthorized as e:
            raise HTTPException(status_code=401, detail="Not authorized")
        except (RuntimeError, anyio.WouldBlock, anyio.EndOfStream) as exc:
            if str(exc) == "No response returned." and await request.is_disconnected():
                return JSONResponse(
                    status_code=204,
                    content={
                        "error": "No response returned",
                        "message": "An unexpected error occurred.",
                    },
                )
            raise
        except Exception as exc:
            log_error(exc, message="Server Exception")
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Internal Server Error",
                    "message": "An unexpected error occurred.",
                },
            )

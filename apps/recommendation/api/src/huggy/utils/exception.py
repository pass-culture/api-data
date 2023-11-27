import traceback
from traceback import print_exception
from http import HTTPStatus
import anyio
from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from huggy.utils.cloud_logging import logger


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
                return Response(status_code=204)
            raise
        except Exception as exc:
            tb = traceback.format_exc()
            logger.error(
                "Exception error",
                extra={
                    "details": {
                        "content": {
                            "error": exc.__class__.__name__,
                            "trace": tb,
                        }
                    }
                },
            )
            raise

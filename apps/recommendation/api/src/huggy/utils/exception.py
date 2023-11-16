import traceback
from traceback import print_exception
from http import HTTPStatus

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from huggy.utils.cloud_logging import logger


class NotAuthorized(Exception):
    pass


class ExceptionHandlerMiddleware(BaseHTTPMiddleware):
    def dispatch(self, request: Request, call_next):
        try:
            return call_next(request)
        except NotAuthorized as e:
            raise HTTPException(status_code=401, detail="Not authorized")

        except Exception as e:
            print_exception(e)
            tb = traceback.format_exc()
            logger.error(
                "Exception error",
                extra={
                    "details": {
                        "content": {
                            "error": e.__class__.__name__,
                            "trace": tb,
                        }
                    }
                },
            )
            raise e

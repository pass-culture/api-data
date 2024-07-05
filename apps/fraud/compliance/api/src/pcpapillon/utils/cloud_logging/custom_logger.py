from fastapi.logger import logger as fastapi_logger


class CustomLogger:
    # Todo : Refactor this class to inherit from logging.Logger for all log levels
    def info(
        self,
        message=None,
        extra=None,
    ):
        log_entry = {
            "message": message,
            "extra": extra,
        }
        fastapi_logger.info(log_entry)

    def debug(
        self,
        message=None,
        extra=None,
    ):
        log_entry = {
            "message": message,
            "extra": extra,
        }
        fastapi_logger.debug(log_entry)

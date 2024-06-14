from fastapi.logger import logger as fastapi_logger


class CustomLogger:
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
        return

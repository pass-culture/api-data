from fastapi.logger import logger


class CustomLogger:
    def info(self, message=None, extra=None):
        log_entry = {"message": message, "extra": extra}
        logger.info(log_entry)
        return

    def warn(self, message=None, extra=None):
        log_entry = {"message": message, "extra": extra}
        logger.warn(log_entry)
        return

    def debug(self, message=None, extra=None):
        log_entry = {"message": message, "extra": extra}
        logger.debug(log_entry)
        return

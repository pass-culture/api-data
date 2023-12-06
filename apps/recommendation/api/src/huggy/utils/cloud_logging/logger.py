from fastapi.logger import logger


from huggy.utils.env_vars import (
    call_id_trace_context,
    ENV_SHORT_NAME,
)


class CustomLogger:
    def info(self, msg=None, extra=None):
        call_id = call_id_trace_context.get()
        log_entry = {"message": msg, "extra": extra, "call_id": call_id}
        logger.info(log_entry)
        return

    def warn(self, msg=None, extra=None):
        call_id = call_id_trace_context.get()
        log_entry = {"message": msg, "extra": extra, "call_id": call_id}
        logger.warn(log_entry)
        return

    def debug(self, msg=None, extra=None):
        call_id = call_id_trace_context.get()
        log_entry = {"message": msg, "extra": extra, "call_id": call_id}
        if ENV_SHORT_NAME != "prod":
            logger.debug(log_entry)
        return

    def error(self, msg=None, extra=None):
        call_id = call_id_trace_context.get()
        log_entry = {"message": msg, "extra": extra, "call_id": call_id}
        logger.error(log_entry)
        return

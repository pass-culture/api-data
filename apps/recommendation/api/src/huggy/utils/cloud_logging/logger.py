from fastapi.logger import logger


from huggy.utils.env_vars import (
    call_id_trace_context,
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
        logger.debug(log_entry)
        return

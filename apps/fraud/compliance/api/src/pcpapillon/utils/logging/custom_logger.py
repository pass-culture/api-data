from pcpapillon.utils.env_vars import call_id_trace_context


class CustomLogger:
    def __init__(self, logger=None):
        self.logger = logger

    def info(
        self,
        message=None,
        extra=None,
    ):
        log_entry = self._format_log(message, extra)
        self.logger.info(log_entry)

    def warn(
        self,
        message=None,
        extra=None,
    ):
        log_entry = self._format_log(message, extra)
        self.logger.warning(log_entry)

    def debug(
        self,
        message=None,
        extra=None,
    ):
        log_entry = self._format_log(message, extra)
        self.logger.debug(log_entry)

    def error(
        self,
        message=None,
        extra=None,
    ):
        log_entry = self._format_log(message, extra)
        self.logger.error(log_entry)

    def _format_log(self, message, extra):
        if extra is None:
            extra = {}
        if message is None:
            message = ""
        call_id = call_id_trace_context.get()
        return {"message": message, "extra": extra, "call_id": call_id}

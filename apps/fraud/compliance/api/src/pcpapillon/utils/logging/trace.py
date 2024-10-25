import uuid

from fastapi import Request
from main import custom_logger
from pcpapillon.utils.env_vars import call_id_trace_context, cloud_trace_context


async def setup_trace(request: Request):
    custom_logger.info("Setting up trace..")
    if "x-cloud-trace-context" in request.headers:
        cloud_trace_context.set(request.headers.get("x-cloud-trace-context"))


async def get_call_id():
    call_id = str(uuid.uuid4())
    call_id_trace_context.set(call_id)
    return call_id

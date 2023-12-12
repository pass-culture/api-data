import uuid

from fastapi import HTTPException, Request

from huggy.utils.env_vars import (
    API_TOKEN,
    API_LOCAL,
    call_id_trace_context,
    cloud_trace_context,
)


async def setup_trace(request: Request):
    if "x-cloud-trace-context" in request.headers:
        cloud_trace_context.set(request.headers.get("x-cloud-trace-context"))


async def check_token(request: Request):
    if API_LOCAL:
        return True
    if request.query_params.get("token", None) != API_TOKEN:
        raise HTTPException(status_code=401, detail="Not authorized")


async def get_call_id():
    call_id = str(uuid.uuid4())
    call_id_trace_context.set(call_id)
    return call_id

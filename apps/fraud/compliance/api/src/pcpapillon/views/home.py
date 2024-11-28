from fastapi import APIRouter, Depends
from main import custom_logger
from pcpapillon.utils.logging.trace import get_call_id, setup_trace

main_router = APIRouter(tags=["home"])


@main_router.get(
    "/",
    dependencies=[Depends(get_call_id), Depends(setup_trace)],
)
async def read_root():
    custom_logger.info("Auth user welcome to : Validation API test")
    return "Auth user welcome to : Validation API test"


@main_router.get(
    "/health/api", dependencies=[Depends(get_call_id), Depends(setup_trace)]
)
async def read_health():
    return "OK"

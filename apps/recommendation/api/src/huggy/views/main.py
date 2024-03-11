from fastapi import APIRouter, Depends
from huggy.utils.cloud_logging import logger
from huggy.views.common import setup_trace


main_router = r = APIRouter(tags=["main"])


@r.get("/", dependencies=[Depends(setup_trace)])
async def read_root():
    logger.info("Welcome to the recommendation API!")
    return "Welcome to the recommendation API!"


@r.get("/health/api")
async def check():
    return "OK"

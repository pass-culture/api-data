from fastapi import APIRouter
from fastapi import Request

from utils.benchmark import log_execution_time


router = APIRouter()


@router.get("/")
@log_execution_time
async def health_check(request: Request) -> dict[str, str]:  # pragma: no cover
    return {"status": "OK", "version": request.app.version}

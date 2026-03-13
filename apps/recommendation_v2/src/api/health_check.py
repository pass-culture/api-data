from fastapi import APIRouter
from fastapi import Request


router = APIRouter()


@router.get("/")
def health_check(request: Request) -> dict[str, str]:
    return {"status": "OK", "version": request.app.version}

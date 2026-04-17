import logging
import tomllib
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import Depends
from fastapi import FastAPI
from fastapi import HTTPException
from fastapi import Query
from fastapi import status

from api.health_check import router as health_check_router
from api.playlist_recommendation import router as playlist_router
from config import settings
from services.logger import logger


def verify_api_token(token: str = Query(...)) -> None:
    """
    Verifies the API token provided in the application's query parameters.

    This function strictly compares the provided token against the expected
    API token defined in the application settings. If they do not match,
    it prevents access by raising an HTTP 401 Unauthorized error.

    Args:
        token (str): The token passed in the query parameters of the HTTP request.

    Raises:
        HTTPException: Raised with status 401 if the token does not match.

    Example:
        A request to an endpoint protected by this dependency would look like:
        > GET /playlist/recommendations?token=my_secret_token

        If `settings.API_TOKEN` is "my_secret_token", access is granted.
        Otherwise, a 401 error is returned.
    """
    # Reject request if the provided token does not match the configured one
    if token != settings.API_TOKEN:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


def get_version() -> str:
    pyproject_path = Path(__file__).resolve().parent.parent / "pyproject.toml"

    try:
        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)
            return data["project"]["version"]
    except (FileNotFoundError, KeyError):
        return "0.0.0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    swagger_url = f"http://127.0.0.1:{settings.FASTAPI_SERVER_PORT}/docs"
    logger.info(
        "🚀 Recommendation API started successfully!",
        extra={"swagger_url": swagger_url, "environment": settings.ENV, "version": app.version},
    )
    yield


app = FastAPI(
    title="pass Culture - Recommendation",
    description="API de recommandation basée sur Vertex AI et FastAPI",
    version=get_version(),
    lifespan=lifespan,
)

# Determine the required dependencies based on the current environment
# In local environments, authentication is bypassed to simplify development
api_token_dependencies = [Depends(verify_api_token)] if not settings.IS_LOCAL else []

app.include_router(playlist_router, tags=["Recommendations"], dependencies=api_token_dependencies)
app.include_router(health_check_router, tags=["Health"])

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=settings.FASTAPI_SERVER_PORT,
        reload=True,
        reload_includes=[".env"],
        log_level=logging.getLevelName(settings.DEBUG_LEVEL).lower(),
    )

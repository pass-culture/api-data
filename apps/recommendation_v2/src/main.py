import logging
import secrets
import tomllib
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import Depends
from fastapi import FastAPI
from fastapi import HTTPException
from fastapi import Security
from fastapi import status
from fastapi.security import APIKeyHeader
from fastapi.security import APIKeyQuery

from api.health_check import router as health_check_router
from api.playlist_recommendation import router as playlist_router
from api.similar_artists import router as similar_artists_router
from api.similar_offer import router as similar_offer_router
from config import settings
from services.db import async_db_engine
from services.logger import logger
from services.redis import redis_cache_service


api_key_query = APIKeyQuery(name="token", auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_token(
    token_query: str | None = Security(api_key_query),
    token_header: str | None = Security(api_key_header),
) -> None:
    """
    Verifies the API token provided either as a query parameter or as an HTTP header.

    The token is accepted from two sources (checked in order):
    - Query parameter  ``?token=<token>``
    - HTTP header  ``X-API-Key: <token>``

    If the token is present in at least one source and matches the configured value,
    the request is accepted. If neither source provides a valid token, an HTTP 401
    Unauthorized error is raised.

    Args:
        token_query (str | None): Token passed via the ``token`` query parameter.
        token_header (str | None): Token passed via the ``X-API-Key`` HTTP header.

    Raises:
        HTTPException: Raised with status 401 if no valid token is found.

    Examples:
        Via query parameter (legacy):
        > GET /playlist/recommendations?token=my_secret_token

        Via HTTP header (preferred):
        > GET /playlist/recommendations
        > X-API-Key: my_secret_token
    """
    token = token_query or token_header

    # TODO (jmontagnat - 2026-06-19): This manual check is required
    #   during the migration phase from query parameters to headers.
    #   Once the transition is complete and all consumers use the header, perform the following cleanup:
    #   1. Remove this manual 'if token is None' check.
    #   2. Set 'auto_error=True' in the 'APIKeyHeader' definition above.
    #   3. Remove the 'APIKeyQuery' dependency entirely.
    if token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    if not secrets.compare_digest(token, settings.API_TOKEN):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


def get_version() -> str:
    """
    Retrieves the application version from the pyproject.toml file.

    It checks two locations for the pyproject.toml file to support both:
    - Local execution (where pyproject.toml is in the parent directory of src/)
    - Docker execution (where pyproject.toml is copied to the same directory as the source code)

    Returns:
        str: The version from pyproject.toml, or "0.0.0" if not found.
    """
    current_dir = Path(__file__).resolve().parent
    # Check parent directory (local run) and current directory (Docker run)
    for pyproject_path in [current_dir.parent / "pyproject.toml", current_dir / "pyproject.toml"]:
        try:
            with open(pyproject_path, "rb") as f:
                data = tomllib.load(f)
                return data["project"]["version"]
        except (FileNotFoundError, KeyError):
            continue
    return "0.0.0"


def show_api_config() -> None:
    config_info = {
        # Environment & Server
        "ENV": settings.ENV,
        "RECOMMENDATION_API_VERSION": settings.RECOMMENDATION_API_VERSION,
        "FASTAPI_SERVER_PORT": settings.FASTAPI_SERVER_PORT,
        "LOG_LEVEL": logging.getLevelName(settings.LOG_LEVEL),
        # Google Cloud & Vertex AI
        "GCP_PROJECT": settings.GCP_PROJECT,
        "VERTEX_RETRIEVAL_ENDPOINT_NAME": settings.VERTEX_RETRIEVAL_ENDPOINT_NAME,
        "VERTEX_RANKING_ENDPOINT_NAME": settings.VERTEX_RANKING_ENDPOINT_NAME,
        "VERTEX_PREDICTION_TIMEOUT": settings.VERTEX_PREDICTION_TIMEOUT,
        "ENABLE_TRACKING_LOGS": settings.ENABLE_TRACKING_LOGS,
    }
    logger.info("🔧 API Configuration", extra=config_info)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await async_db_engine.dispose()
    await redis_cache_service.connect()

    swagger_url = f"http://127.0.0.1:{settings.FASTAPI_SERVER_PORT}/docs"
    show_api_config()
    logger.info(
        "🚀 Recommendation API started successfully !"
        f" Redis Cache: {'ENABLED 🟢' if settings.REDIS_CACHE_ENABLED else 'DISABLED 🔴'}",
        extra={
            "swagger_url": swagger_url,
            "environment": settings.ENV,
            "version": app.version,
            "redis_enabled": settings.REDIS_CACHE_ENABLED,
        },
    )

    yield

    await async_db_engine.dispose()
    await redis_cache_service.disconnect()


app = FastAPI(
    title="pass Culture - Recommendation",
    description="API de recommandation basée sur Vertex AI et FastAPI",
    version=get_version(),
    lifespan=lifespan,
)

# Determine the required dependencies based on the current environment
# In local environments, authentication is bypassed to simplify development
api_token_dependencies = [Depends(verify_api_token)] if not settings.IS_LOCAL else []

app.include_router(health_check_router, tags=["Health"])
app.include_router(similar_offer_router, tags=["Similar Offers"], dependencies=api_token_dependencies)
app.include_router(playlist_router, tags=["Recommendations"], dependencies=api_token_dependencies)
app.include_router(similar_artists_router, tags=["Similar Artists"], dependencies=api_token_dependencies)
if __name__ == "__main__":  # pragma: no cover
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=settings.FASTAPI_SERVER_PORT,
        reload=True,
        reload_includes=[".env"],
        log_level=logging.getLevelName(settings.LOG_LEVEL).lower(),
    )

import logging
import secrets
import tomllib
import traceback
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import Depends
from fastapi import FastAPI
from fastapi import HTTPException
from fastapi import Request
from fastapi import Security
from fastapi import status
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from sqlalchemy.exc import SQLAlchemyError

from api.health_check import router as health_check_router
from api.offer_page_playlists import router as offer_page_playlists_router
from api.playlist_recommendation import router as playlist_router
from api.playlist_top_artists import router as playlist_top_artists_router
from api.similar_artists import router as similar_artists_router
from api.similar_offer import router as similar_offer_router
from config import settings
from middleware.gcp_trace import GCPTraceMiddleware
from services.db import async_db_engine
from services.logger import logger
from services.redis import redis_cache_service


api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)


def verify_api_token(token: str = Security(api_key_header)) -> None:
    """
    Verifies the API token provided in the ``X-API-Key`` HTTP header.

    Args:
        token (str): Token passed via the ``X-API-Key`` HTTP header.

    Raises:
        HTTPException: Raised with status 401 if the header is missing or the token is invalid.

    Examples:
        > GET /playlist/recommendations
        > X-API-Key: my_secret_token
    """

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
        "AB_TEST_VARIANT_LABEL": settings.AB_TEST_VARIANT_LABEL,
        # Google Cloud & Vertex AI
        "GCP_PROJECT": settings.GCP_PROJECT,
        "VERTEX_RETRIEVAL_ENDPOINT_NAME": settings.VERTEX_RETRIEVAL_ENDPOINT_NAME,
        "VERTEX_RANKING_ENDPOINT_NAME": settings.VERTEX_RANKING_ENDPOINT_NAME,
        "VERTEX_PREDICTION_TIMEOUT": settings.VERTEX_PREDICTION_TIMEOUT,
        "ENABLE_TRACKING_LOGS": settings.ENABLE_TRACKING_LOGS,
        # Redis — master switch
        "REDIS_CACHE_ENABLED": settings.REDIS_CACHE_ENABLED,
        # Redis — cache strategies
        "ENDPOINT_RESPONSE_CACHE_ENABLED": settings.ENDPOINT_RESPONSE_CACHE_ENABLED,
        "OFFER_RESOLUTION_CACHE_ENABLED": settings.OFFER_RESOLUTION_CACHE_ENABLED,
        # Redis — tuning
        "OFFER_RESOLUTION_CACHE_H3_RESOLUTION": settings.OFFER_RESOLUTION_CACHE_H3_RESOLUTION,
        "ENDPOINT_RESPONSE_CACHE_H3_RESOLUTION": settings.ENDPOINT_RESPONSE_CACHE_H3_RESOLUTION,
        # Geospatial
        "GEOSPATIAL_RETRIEVAL_H3_RESOLUTION": settings.GEOSPATIAL_RETRIEVAL_H3_RESOLUTION,
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
        f" Redis: {'ENABLED 🟢' if settings.REDIS_CACHE_ENABLED else 'DISABLED 🔴'}"
        f" | Endpoint cache: {'🟢' if settings.ENDPOINT_RESPONSE_CACHE_ENABLED else '🔴'}"
        f" | Offer resolution cache: {'🟢' if settings.OFFER_RESOLUTION_CACHE_ENABLED else '🔴'}",
        extra={
            "swagger_url": swagger_url,
            "environment": settings.ENV,
            "version": app.version,
            "redis_enabled": settings.REDIS_CACHE_ENABLED,
            "endpoint_response_cache_enabled": settings.ENDPOINT_RESPONSE_CACHE_ENABLED,
            "offer_resolution_cache_enabled": settings.OFFER_RESOLUTION_CACHE_ENABLED,
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

app.add_middleware(GCPTraceMiddleware)  # ty: ignore[invalid-argument-type]


@app.exception_handler(SQLAlchemyError)
async def database_exception_handler(request: Request, exc: SQLAlchemyError):
    underlying_error = getattr(exc, "orig", exc)
    exact_error_name = type(underlying_error).__name__
    route = request.scope.get("route")
    route_template = route.path if route else request.url.path

    body_content = None
    if request.method != "GET":
        body_content = await request.json()

    logger.error(
        f"🚨 Database error [{exact_error_name}] on {request.method} {route_template}",
        extra={
            "database_error_type": exact_error_name,
            "database_error_detail": str(underlying_error),
            "route_template": route_template,
            "path": request.url.path,
            "method": request.method,
            "query_params": dict(request.query_params),
            "body": body_content,
            "traceback": traceback.format_exc(),
        },
    )

    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": "Service temporarily unavailable. Please try again later."},
    )


# Determine the required dependencies based on the current environment
# In local environments, authentication is bypassed to simplify development
api_token_dependencies = [Depends(verify_api_token)] if not settings.IS_LOCAL else []

app.include_router(health_check_router, tags=["Health"])
app.include_router(similar_offer_router, tags=["Similar Offers"], dependencies=api_token_dependencies)
app.include_router(offer_page_playlists_router, tags=["Offer Page Playlists"], dependencies=api_token_dependencies)
app.include_router(playlist_router, tags=["Recommendations"], dependencies=api_token_dependencies)
app.include_router(similar_artists_router, tags=["Similar Artists"], dependencies=api_token_dependencies)
app.include_router(playlist_top_artists_router, tags=["Playlist Top Artists"], dependencies=api_token_dependencies)
if __name__ == "__main__":  # pragma: no cover
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=settings.FASTAPI_SERVER_PORT,
        reload=True,
        reload_includes=[".env"],
        log_level=logging.getLevelName(settings.LOG_LEVEL).lower(),
    )

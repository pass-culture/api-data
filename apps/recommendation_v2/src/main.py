import tomllib
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI

from api.health_check import router as health_check_router
from api.playlist_recommendation import router as playlist_router
from config import settings
from services.logger import logger


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
        extra_data={"swagger_url": swagger_url, "environment": settings.ENV, "version": app.version},
    )
    yield


app = FastAPI(
    title="pass Culture - Recommendation",
    description="API de recommandation basée sur Vertex AI et FastAPI",
    version=get_version(),
    lifespan=lifespan,
)

app.include_router(playlist_router, tags=["Recommendations"])
app.include_router(health_check_router, tags=["Health"])

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=settings.FASTAPI_SERVER_PORT, reload=True, reload_includes=[".env"])

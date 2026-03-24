import logging
import tomllib
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from api.health_check import router as health_check_router
from api.playlist_recommendation import router as playlist_router
from api.similar_offer import router as similar_offer_router
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
        extra={"swagger_url": swagger_url, "environment": settings.ENV, "version": app.version},
    )
    yield


app = FastAPI(
    title="pass Culture - Recommendation",
    description="API de recommandation basée sur Vertex AI et FastAPI",
    version=get_version(),
    lifespan=lifespan,
    docs_url=None,
)

static_path = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_path), name="static")


@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    swagger_ui = get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=app.title + " - Swagger UI",
        oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
    )
    body = swagger_ui.body.decode("utf-8")
    # Inject custom CSS after the default CSS
    body = body.replace("</head>", '<link type="text/css" rel="stylesheet" href="/static/styles.css"></head>')
    return HTMLResponse(content=body)


app.include_router(playlist_router, tags=["Recommendations"])
app.include_router(similar_offer_router, tags=["Recommendations"])
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

import tomllib
from pathlib import Path

from fastapi import FastAPI

from api.playlist_recommendation import router as playlist_router


def get_version() -> str:
    pyproject_path = Path(__file__).resolve().parent.parent / "pyproject.toml"

    try:
        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)
            return data["project"]["version"]
    except (FileNotFoundError, KeyError):
        return "0.0.0"


app = FastAPI(
    title="pass Culture - Recommendation",
    description="API de recommandation basée sur Vertex AI et FastAPI",
    version=get_version(),
)

app.include_router(playlist_router, tags=["Recommendations"])


@app.get("/")
def health_check() -> dict[str, str]:
    return {"status": "OK", "version": app.version}

from fastapi import FastAPI, Request
from fastapi_versioning import VersionedFastAPI
from pcpapillon.utils.cloud_logging.setup import setup_logging
from pcpapillon.utils.env_vars import (
    cloud_trace_context,
)


async def setup_trace(request: Request):
    custom_logger.info("Setting up trace..")
    if "x-cloud-trace-context" in request.headers:
        cloud_trace_context.set(request.headers.get("x-cloud-trace-context"))


custom_logger = setup_logging()


def init_app():
    from pcpapillon.views.compliance import compliance_router
    from pcpapillon.views.main import main_router

    app = FastAPI(title="Passculture offer validation API")

    app.include_router(main_router, tags=["main"])
    app.include_router(compliance_router, tags=["compliance"])
    return VersionedFastAPI(app, enable_latest=True)


app = init_app()

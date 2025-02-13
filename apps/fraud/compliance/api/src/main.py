from fastapi import FastAPI
from fastapi_versioning import VersionedFastAPI
from pcpapillon.utils.logging.setup import setup_logging

custom_logger = setup_logging()


def init_app():
    from pcpapillon.views.compliance import compliance_router
    from pcpapillon.views.home import main_router

    app = FastAPI(title="Passculture offer validation API")

    app.include_router(main_router, tags=["home"])
    app.include_router(compliance_router, tags=["compliance"])
    return VersionedFastAPI(app, enable_latest=True)


app = init_app()

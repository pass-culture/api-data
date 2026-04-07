from fastapi import FastAPI
from fastapi_versioning import VersionedFastAPI

from pcpapillon.utils.logging.setup import setup_logging

custom_logger = setup_logging()


def init_app():
    from pcpapillon.views.compliance import compliance_router, init_compliance_model
    from pcpapillon.views.home import main_router
    from pcpapillon.views.search_edito import search_edito_router

    app = FastAPI(title="Passculture offer validation API")

    # Add startup event to load models after the app binds to port
    @app.on_event("startup")
    async def startup_event():
        custom_logger.info("Application startup: loading ML models...")
        init_compliance_model()
        custom_logger.info("Application startup complete")

    app.include_router(main_router, tags=["home"])
    app.include_router(compliance_router, tags=["compliance"])
    app.include_router(search_edito_router, tags=["search_edito"])
    return VersionedFastAPI(app, enable_latest=True)


app = init_app()

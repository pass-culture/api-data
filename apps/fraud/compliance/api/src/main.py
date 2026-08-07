from fastapi import FastAPI
from fastapi_versioning import VersionedFastAPI


def init_app():
    from pcpapillon.views.compliance import compliance_router
    from pcpapillon.views.home import main_router
    from pcpapillon.views.search_edito import search_edito_router

    app = FastAPI(title="Passculture offer validation API")

    app.include_router(main_router, tags=["home"])
    app.include_router(compliance_router, tags=["compliance"])
    app.include_router(search_edito_router, tags=["search_edito"])
    return VersionedFastAPI(app, enable_latest=True)


app = init_app()

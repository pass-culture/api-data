from contextlib import asynccontextmanager
from fastapi import FastAPI
from huggy.database.config import config
from huggy.database.database import sessionmanager
from huggy.utils.env_vars import (
    CORS_ALLOWED_ORIGIN,
)


def init_app(init_db=True):
    lifespan = None

    if init_db:
        sessionmanager.init(config.DB_CONFIG)

        @asynccontextmanager
        async def lifespan(app: FastAPI):
            try:
                yield
            finally:
                if sessionmanager._engine is not None:
                    await sessionmanager.close()

    server = FastAPI(title="passCulture - Recommendation", lifespan=lifespan)
    server = include_routers(server)
    server = include_middleware(server)
    return server


def include_middleware(server):
    from fastapi.middleware.cors import CORSMiddleware
    from huggy.utils.exception import ExceptionHandlerMiddleware

    server.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ALLOWED_ORIGIN,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    server.add_middleware(ExceptionHandlerMiddleware)
    return server


def include_routers(server):
    from huggy.views.offer import offer_router
    from huggy.views.main import main_router
    from huggy.views.home import home_router

    server.include_router(offer_router, tags=["offer"])
    server.include_router(home_router, tags=["home"])
    server.include_router(main_router, tags=["main"])
    return server

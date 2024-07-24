import os

from huggy.utils.env_vars import (
    SQL_BASE_DATABASE,
    SQL_BASE_HOST,
    SQL_BASE_PASSWORD,
    SQL_BASE_PORT,
    SQL_BASE_USER,
)


class Config:
    DB_CONFIG = os.getenv(
        "DB_CONFIG",
        "postgresql+asyncpg://{SQL_BASE_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}".format(
            SQL_BASE_USER=SQL_BASE_USER,
            DB_PASSWORD=SQL_BASE_PASSWORD,
            DB_HOST=f"{SQL_BASE_HOST}:{SQL_BASE_PORT}",
            DB_NAME=SQL_BASE_DATABASE,
        ),
    )


config = Config

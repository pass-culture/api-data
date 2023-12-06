import typing as t

from sqlalchemy import engine, inspect
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from huggy.utils.env_vars import (
    API_LOCAL,
    DATA_GCP_TEST_POSTGRES_PORT,
    DB_NAME,
    SQL_BASE,
    SQL_BASE_PASSWORD,
    SQL_BASE_USER,
    SQL_HOST,
    SQL_PORT,
)


async def get_table_names(session: AsyncSession) -> t.List[str]:
    def __get(engine):
        inspector = inspect(engine)
        return inspector.get_table_names()

    async with session.bind.connect() as connection:
        return await connection.run_sync(__get)


async def check_table_exists(session: AsyncSession, table_name: str) -> bool:
    def __get(engine):
        inspector = inspect(engine)
        return inspector.has_table(table_name)

    async with session.bind.connect() as connection:
        return await connection.run_sync(__get)


def get_engine(local=API_LOCAL):
    if local:
        conn = f"postgresql+asyncpg://postgres:postgres@localhost:{DATA_GCP_TEST_POSTGRES_PORT}/{DB_NAME}"

    else:
        conn = engine.url.URL(
            drivername="postgresql+asyncpg",
            username=SQL_BASE_USER,
            password=SQL_BASE_PASSWORD,
            database=SQL_BASE,
            host=SQL_HOST,
            port=SQL_PORT,
            query={},
        )
    return create_async_engine(
        conn,
        pool_size=5,
        max_overflow=10,
        pool_timeout=10,
        pool_pre_ping=True,
        pool_recycle=1000,
    )

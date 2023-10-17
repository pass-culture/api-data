import typing as t
from abc import abstractmethod

from fastapi.logger import logger
from sqlalchemy import engine, inspect
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker

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

query = {}


def get_engine():
    if API_LOCAL:
        return create_async_engine(
            f"postgresql+asyncpg://postgres:postgres@localhost:{DATA_GCP_TEST_POSTGRES_PORT}/{DB_NAME}"
        )

    else:
        return create_async_engine(
            engine.url.URL(
                drivername="postgresql+asyncpg",
                username=SQL_BASE_USER,
                password=SQL_BASE_PASSWORD,
                database=SQL_BASE,
                host=SQL_HOST,
                port=SQL_PORT,
                query=query,
            ),
            pool_size=3,
            max_overflow=15,
            pool_timeout=30,
            pool_recycle=1800,
            client_encoding="utf8",
        )


Base = declarative_base()


class MaterializedBase:
    @abstractmethod
    def materialized_tables(self) -> t.List[Base]:
        pass

    async def get_available_table(self, session: AsyncSession) -> Base:
        table_names = []
        for obj in self.materialized_tables():
            try:
                table_name = obj.__tablename__
                table_names.append(table_name)
                if await check_table_exists(session, table_name):
                    return obj
            except NameError:
                print(f"Model {obj} is not defined")
        raise Exception(f"Tables :  {', '.join(table_names)} not found.")


async def get_db() -> AsyncSession:
    AsyncSessionLocal = sessionmaker(
        bind=get_engine(),
        expire_on_commit=False,
        class_=AsyncSession,
    )
    async with AsyncSessionLocal() as session:
        yield session


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

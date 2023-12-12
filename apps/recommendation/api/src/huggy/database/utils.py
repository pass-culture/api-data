import typing as t

from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncSession


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

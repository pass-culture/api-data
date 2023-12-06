from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

from huggy.database.utils import get_engine


def async_session_generator():
    async_engine = get_engine()
    # async_engine.execution_options(**{"statement_timeout": 1})
    return sessionmaker(
        bind=async_engine,
        expire_on_commit=False,
        class_=AsyncSession,
    )


async def get_db() -> AsyncSession:
    async_session = async_session_generator()

    async with async_session() as session:
        try:
            yield session
        except:
            await session.rollback()
            raise
        finally:
            await session.close()

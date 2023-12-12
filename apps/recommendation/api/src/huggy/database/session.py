from huggy.database.database import sessionmanager
from sqlalchemy.ext.asyncio import AsyncSession


async def get_db() -> AsyncSession:
    async with sessionmanager.session() as session:
        yield session

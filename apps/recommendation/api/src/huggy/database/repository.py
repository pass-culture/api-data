from typing import Any, Generic, Optional, TypeVar

from huggy.database.base import Base
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T", bound=Base)


class BaseRepository(Generic[T]):
    def __init__(self, session: AsyncSession, model: type[T]):
        self.session = session
        self.model = model

    async def get_by_id(self, id: Any) -> Optional[T]:
        """Get a single record by ID"""
        result = await self.session.execute(
            select(self.model).where(self.model.id == id)
        )
        return result.scalar_one_or_none()

    async def get_all(self, limit: Optional[int] = None, offset: int = 0) -> list[T]:
        """Get all records with optional pagination"""
        query = select(self.model).offset(offset)
        if limit:
            query = query.limit(limit)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def create(self, **kwargs) -> T:
        """Create a new record"""
        instance = self.model(**kwargs)
        self.session.add(instance)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def update(self, id: Any, **kwargs) -> Optional[T]:
        """Update a record by ID"""
        await self.session.execute(
            update(self.model).where(self.model.id == id).values(**kwargs)
        )
        return await self.get_by_id(id)

    async def delete(self, id: Any) -> bool:
        """Delete a record by ID"""
        result = await self.session.execute(
            delete(self.model).where(self.model.id == id)
        )
        return result.rowcount > 0

    async def exists(self, **filters) -> bool:
        """Check if a record exists with given filters"""
        query = select(self.model).filter_by(**filters).limit(1)
        result = await self.session.execute(query)
        return result.scalar_one_or_none() is not None


class MaterializedViewRepository(BaseRepository[T]):
    """Repository for handling materialized views with fallback logic"""

    def __init__(
        self,
        session: AsyncSession,
        model: type[T],
        fallback_tables: list[type[T]] | None = None,
    ):
        super().__init__(session, model)
        self.fallback_tables = fallback_tables or []

    async def get_available_model(self) -> type[T]:
        """Get the first available materialized view table"""
        from huggy.database.utils import check_table_exists

        # Check main model first
        if await check_table_exists(self.session, self.model.__tablename__):
            return self.model

        # Check fallback tables
        for fallback_model in self.fallback_tables:
            if await check_table_exists(self.session, fallback_model.__tablename__):
                return fallback_model

        raise Exception(f"No available table found for {self.model.__name__}")

    async def query(self):
        """Get a query object for the available table"""
        available_model = await self.get_available_model()
        return select(available_model)

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine

from config import settings


# --- 1. Database Engine Initialization ---
# Create an asynchronous SQLAlchemy engine.
# pool_pre_ping=True ensures connections are verified before being leased from the pool.
async_db_engine = create_async_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=15,
    max_overflow=15,
    echo=False,
)


# --- 2. Session Factory ---
# Acts as a factory for creating new AsyncSession instances per request.
AsyncSessionFactory = async_sessionmaker(
    bind=async_db_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


# --- 3. FastAPI Dependency ---
async def get_database_session() -> AsyncGenerator[AsyncSession]:
    """
    FastAPI dependency that provides an asynchronous database session.

    This generator manages the database connection lifecycle for a single HTTP request.
    It yields an active session to the route handler and ensures it is safely closed
    (and returned to the connection pool) once the request is completed or if an error occurs.

    Yields:
        AsyncSession: An active SQLAlchemy asynchronous session.
    """
    async with AsyncSessionFactory() as session:
        yield session

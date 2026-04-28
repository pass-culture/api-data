import asyncio
import uuid
from unittest.mock import patch

import pytest
import pytest_asyncio
import sqlalchemy as sa
from httpx import ASGITransport
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool
from testcontainers.postgres import PostgresContainer

from config import settings
from main import app
from models.base import Base
from services.db import get_database_session

from tests.factories.models import factory_session
from tests.factories.schemas import VertexPredictionResultFactory


MOCK_CALL_ID = "12345678-1234-5678-1234-567812345678"

settings.REDIS_CACHE_ENABLED = False


@pytest.fixture(scope="session")
def postgres_container():
    """
    Start a Docker container running PostgreSQL with PostGIS for the test session.

    Yields the container instance so dependent fixtures can retrieve the connection URL.
    The container is automatically stopped once the session ends.
    """
    with PostgresContainer(image="postgis/postgis:15-3.3-alpine") as postgres:
        yield postgres


@pytest.fixture(scope="session", autouse=True)
def mock_uuid():
    """
    Replace UUID generation with a fixed, predictable value for the entire test session.

    All call_ids generated via ``core.pipeline.uuid.uuid4`` will return ``MOCK_CALL_ID``,
    making snapshot assertions deterministic across runs.
    """
    with (
        patch("controllers.pipeline_playlist_recommendation.uuid.uuid4") as mock_uuid_playlist,
        patch("controllers.pipeline_similar_offer.uuid.uuid4") as mock_uuid_similar,
    ):
        mock_uuid_playlist.return_value = uuid.UUID(MOCK_CALL_ID)
        mock_uuid_similar.return_value = uuid.UUID(MOCK_CALL_ID)
        yield (mock_uuid_playlist, mock_uuid_similar)


@pytest.fixture(autouse=True)
def mock_vertex_retrieval(mocker):
    """
    Replace the Vertex AI candidate-retrieval call with a pre-built factory result.

    The mock is applied to ``core.pipeline.fetch_candidate_items_from_vertex`` so every
    test that exercises the pipeline receives a consistent, offline response.
    """
    mock_retrieval = mocker.patch(
        "core.pipeline.fetch_candidate_items_from_vertex",
        new_callable=mocker.AsyncMock,
    )
    mock_retrieval.return_value = VertexPredictionResultFactory.build()

    return mock_retrieval


@pytest.fixture(autouse=True)
def mock_vertex_ranking(mocker):
    """
    Replace the Vertex AI ranking call with an identity function.

    ``core.pipeline.rank_and_sort_offers_with_vertex`` is patched so that it returns
    the input offers unchanged, removing any dependency on the live ranking service.
    """
    mock_rank = mocker.patch(
        "core.pipeline.rank_and_sort_offers_with_vertex",
        new_callable=mocker.AsyncMock,
    )
    mock_rank.side_effect = lambda offers, user_context: offers

    return mock_rank


@pytest.fixture(scope="session")
def engine(postgres_container):
    """
    Create an async SQLAlchemy engine connected to the Testcontainers PostgreSQL instance.

    The PostGIS extension is enabled and the full ORM schema is created before the
    fixture yields. The engine is disposed of at the end of the session.
    """
    db_url = postgres_container.get_connection_url().replace("psycopg2", "asyncpg")

    async_engine = create_async_engine(db_url, echo=False, poolclass=NullPool)

    async def _initialize_database_schema():
        async with async_engine.begin() as connection:
            await connection.execute(sa.text("CREATE EXTENSION IF NOT EXISTS postgis"))
            await connection.run_sync(Base.metadata.create_all)

    asyncio.run(_initialize_database_schema())

    yield async_engine

    asyncio.run(async_engine.dispose())


@pytest_asyncio.fixture()
async def db_session(engine):
    """
    Provide an isolated async database session for a single test.

    The session is wrapped in a transaction that is always rolled back after the test,
    keeping the database clean without the overhead of re-creating the schema.

    Schema
    ------
    engine ──► connection ──► transaction (rolled back on teardown)
                                   └──► AsyncSession (yielded to test)
    """
    connection = await engine.connect()
    transaction = await connection.begin()

    session = AsyncSession(bind=connection, expire_on_commit=False)
    context_token = factory_session.set(session)

    yield session

    factory_session.reset(context_token)
    await session.close()
    await transaction.rollback()
    await connection.close()


@pytest_asyncio.fixture()
async def client(db_session):
    """
    Provide an async HTTP client pointed at the FastAPI application.

    The application's database dependency is overridden with the test session so all
    requests share the same rolled-back transaction, guaranteeing isolation.
    """

    async def override_get_database_session():
        yield db_session

    app.dependency_overrides[get_database_session] = override_get_database_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as async_client:
        yield async_client

    app.dependency_overrides.clear()

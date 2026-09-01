import asyncio
import socket as _socket_module
import uuid
from collections.abc import Generator
from unittest.mock import AsyncMock
from unittest.mock import patch

import pytest
import pytest_asyncio
import sqlalchemy as sa
from httpx import ASGITransport
from httpx import AsyncClient
from pytest_socket import disable_socket
from pytest_socket import enable_socket
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool
from testcontainers.postgres import PostgresContainer
from testcontainers.redis import RedisContainer

from config import settings
from connectors.vertex_api import VertexAPI
from main import app
from models.base import Base
from services.db import get_database_session
from services.redis import redis_cache_service

from tests.factories.models import factory_session
from tests.factories.schemas import RecommendableItemFactory
from tests.factories.schemas import VertexPredictionResultFactory


MOCK_CALL_ID = "12345678-1234-5678-1234-567812345678"

settings.REDIS_CACHE_ENABLED = False


# ---------------------------------------------------------------------------
# Cache test helpers
# ---------------------------------------------------------------------------


def patch_all_caches_enabled(mocker) -> None:
    """
    Enable the Redis master switch and all cache strategy flags atomically.

    Use this helper in tests instead of patching REDIS_CACHE_ENABLED alone.

    Why this is needed:
    ENDPOINT_RESPONSE_CACHE_ENABLED, OFFER_RESOLUTION_CACHE_ENABLED
    flags are pre-computed from REDIS_CACHE_ENABLED at settings
    module load time. Patching only REDIS_CACHE_ENABLED at runtime (via mocker)
    does NOT cascade to the strategy flags — they keep the value they had at import
    time. This helper patches all flags atomically, mirroring the production
    behaviour of REDIS_CACHE_ENABLED=True.
    """
    mocker.patch.object(settings, "REDIS_CACHE_ENABLED", new=True)
    mocker.patch.object(settings, "ENDPOINT_RESPONSE_CACHE_ENABLED", new=True)
    mocker.patch.object(settings, "OFFER_RESOLUTION_CACHE_ENABLED", new=True)


def patch_all_caches_disabled(mocker) -> None:
    """
    Disable the Redis master switch and all cache strategy flags atomically.

    Use this helper in tests instead of patching REDIS_CACHE_ENABLED alone.

    Why this is needed:
    Strategy flags are pre-computed at module load time, so patching only the master
    switch at runtime does not disable them. This helper patches all flags atomically,
    mirroring the production behaviour of REDIS_CACHE_ENABLED=False.
    """
    mocker.patch.object(settings, "REDIS_CACHE_ENABLED", new=False)
    mocker.patch.object(settings, "ENDPOINT_RESPONSE_CACHE_ENABLED", new=False)
    mocker.patch.object(settings, "OFFER_RESOLUTION_CACHE_ENABLED", new=False)


# ---------------------------------------------------------------------------
# Marker auto-assignment
# ---------------------------------------------------------------------------

_INTEGRATION_FIXTURES = {"db_session", "client", "redis_service"}


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Auto-apply unit / integration markers based on fixture usage."""
    for item in items:
        names = set(getattr(item, "fixturenames", []))
        if names.intersection(_INTEGRATION_FIXTURES):
            item.add_marker(pytest.mark.integration)
        else:
            item.add_marker(pytest.mark.unit)


# ---------------------------------------------------------------------------
# Network blocking (all tests)
# ---------------------------------------------------------------------------

# Hosts reachable from integration tests (Docker containers bind to localhost).
_LOCALHOST_HOSTS = {"localhost", "127.0.0.1", "::1"}


@pytest.fixture(autouse=True)
def block_network_calls_in_tests(request: pytest.FixtureRequest) -> Generator[None]:
    """
    Enforce strict network isolation depending on the test type.

    **Unit tests** — all TCP/UDP socket creation is blocked via pytest-socket.
    Any accidental call to an external service raises ``SocketBlockedError``
    immediately. Unix-domain sockets are still allowed so the asyncio event
    loop can create its internal ``socketpair()``.

    **Integration tests** — socket creation is allowed (Docker containers need
    it), but ``socket.getaddrinfo`` is patched so that DNS resolution for any
    host outside ``localhost / 127.0.0.1 / ::1`` is both blocked *and* recorded.
    Blocking alone is not enough: network libraries often swallow
    ``ConnectionRefusedError`` internally, masking the violation.  The fixture
    therefore collects every blocked attempt and calls ``pytest.fail()`` in
    teardown, which is *never* swallowed by application code.

    Parameters
    ----------
    request:
        Pytest's built-in fixture providing access to the current test's markers
        and metadata, used here to distinguish ``unit`` from ``integration`` tests.

    Yields
    ------
    None
        Control is yielded to the test body; cleanup runs after the test finishes.
    """
    if request.node.get_closest_marker("unit"):
        disable_socket(allow_unix_socket=True)
        yield
        enable_socket()

    elif request.node.get_closest_marker("integration"):
        original_getaddrinfo = _socket_module.getaddrinfo
        blocked_external_hosts: list[str] = []

        def _guarded_getaddrinfo(host, port, *args, **kwargs):
            if isinstance(host, str) and host not in _LOCALHOST_HOSTS:
                blocked_external_hosts.append(host)
                raise ConnectionRefusedError(
                    f"[TEST GUARD] DNS resolution for external host '{host}' is blocked "
                    "in integration tests. Only localhost connections (Docker containers) "
                    "are allowed — use mocks for all other external services."
                )
            return original_getaddrinfo(host, port, *args, **kwargs)

        _socket_module.getaddrinfo = _guarded_getaddrinfo  # ty: ignore[invalid-assignment]
        yield
        _socket_module.getaddrinfo = original_getaddrinfo

        if blocked_external_hosts:
            pytest.fail(
                f"Test made unexpected network call(s) to external host(s): "
                f"{blocked_external_hosts}. "
                "Only localhost connections (Docker containers) are allowed. "
                "Ensure all external services are properly mocked."
            )

    else:
        yield


# ---------------------------------------------------------------------------
# Global autouse mocks (apply to every test)
# ---------------------------------------------------------------------------


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
        patch("controllers.pipeline_similar_artists.uuid.uuid4") as mock_uuid_artists,
    ):
        mock_uuid_playlist.return_value = uuid.UUID(MOCK_CALL_ID)
        mock_uuid_similar.return_value = uuid.UUID(MOCK_CALL_ID)
        mock_uuid_artists.return_value = uuid.UUID(MOCK_CALL_ID)
        yield (mock_uuid_playlist, mock_uuid_similar, mock_uuid_artists)


@pytest.fixture(autouse=True)
def mock_vertex_retrieval(mocker):
    """
    Replace the Vertex AI candidate-retrieval call with a pre-built factory result.

    The mock is applied to all controllers so every test that exercises the pipeline
    receives a consistent, offline response without touching the real Vertex AI service.

    Functions patched
    -----------------
    - ``fetch_all_playlist_recommendation_retrieval_predictions_from_vertex`` (playlist pipeline)
      → returns a ``list[RecommendableItem]`` directly (already merged and deduplicated).
    - ``fetch_retrieval_predictions_from_vertex`` (similar-offer pipeline, standard path)
      → returns a ``VertexPredictionResult``.
    - ``fetch_graph_predictions_from_vertex`` (similar-offer pipeline, ``retrieval_model=graph`` path)
      → returns a ``VertexPredictionResult``.
    """
    mock_retrieval_playlist = mocker.patch(
        "controllers.pipeline_playlist_recommendation.fetch_all_playlist_recommendation_retrieval_predictions_from_vertex",
        new_callable=mocker.AsyncMock,
    )
    mock_retrieval_similar = mocker.patch(
        "controllers.pipeline_similar_offer.fetch_retrieval_predictions_from_vertex",
        new_callable=mocker.AsyncMock,
    )
    mock_retrieval_graph = mocker.patch(
        "controllers.pipeline_similar_offer.fetch_graph_predictions_from_vertex",
        new_callable=mocker.AsyncMock,
    )
    mock_retrieval_playlist.return_value = RecommendableItemFactory.batch(10)
    mock_retrieval_similar.return_value = VertexPredictionResultFactory.build()
    mock_retrieval_graph.return_value = VertexPredictionResultFactory.build()

    return mock_retrieval_playlist, mock_retrieval_similar, mock_retrieval_graph


@pytest.fixture(autouse=True)
def mock_vertex_ranking(mocker):
    """
    Replace the Vertex AI ranking call with an identity function.

    Both controllers are patched so that ``rank_and_sort_offers_with_vertex`` returns
    the input offers unchanged, removing any dependency on the live ranking service.
    """
    mock_rank_playlist = mocker.patch(
        "controllers.pipeline_playlist_recommendation.rank_and_sort_offers_with_vertex",
        new_callable=mocker.AsyncMock,
    )
    mock_rank_similar = mocker.patch(
        "controllers.pipeline_similar_offer.rank_and_sort_offers_with_vertex",
        new_callable=mocker.AsyncMock,
    )
    mock_rank_playlist.side_effect = lambda offers, user_context: offers
    mock_rank_similar.side_effect = lambda offers, user_context: offers

    return mock_rank_playlist, mock_rank_similar


# ---------------------------------------------------------------------------
# PostgreSQL integration fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def postgres_container():
    """
    Start a Docker container running PostgreSQL with PostGIS for the test session.

    Yields the container instance so dependent fixtures can retrieve the connection URL.
    The container is automatically stopped once the session ends.
    """
    with PostgresContainer(image="postgis/postgis:15-3.3-alpine") as postgres:
        yield postgres


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
    Provide an async database session for a single test.

    Unlike the classic "open connection + begin transaction + roll back on teardown"
    recipe, this session's commits are **real** (the session is bound directly to the
    ``engine``, not to a pre-opened ``Connection`` already wrapped in an external
    transaction — the latter turns ``Session.commit()`` into a no-op "subtransaction"
    commit that is invisible to any other connection).

    Why this matters
    -----------------
    ``pipeline_offer_page_playlists`` opens its *own* concurrent ``AsyncSession``
    objects via ``AsyncSessionFactory`` (see the ``client`` fixture below), each one
    borrowing a **different physical connection** from the same pool — required so
    that concurrently-scheduled coroutines never share a single connection (asyncpg/
    SQLAlchemy forbid concurrent operations on one connection).
    PostgreSQL isolation guarantees that an uncommitted transaction on one connection
    is *never* visible from another connection, no matter the isolation level. So any
    fixture data seeded through ``db_session`` (e.g. via factories, which call
    ``session.commit()``) must be genuinely committed, or it would silently stay
    invisible to those parallel sessions — causing hard-to-debug empty results
    instead of a clear failure.

    Test isolation is instead guaranteed by truncating every table after the test
    (see teardown below) rather than relying on a rolled-back transaction.

    Schema
    ------
    engine ──► AsyncSession (real commits, yielded to test)
    teardown: TRUNCATE every table (all data, however committed, is wiped)
    """
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    session = session_factory()
    context_token = factory_session.set(session)

    yield session

    factory_session.reset(context_token)
    await session.close()

    # Real commits (see docstring above) mean data is genuinely persisted, so a
    # rollback is no longer enough to clean up: explicitly truncate every table.
    async with engine.begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            await connection.execute(table.delete())


@pytest_asyncio.fixture()
async def client(db_session, engine):
    """
    Provide an async HTTP client pointed at the FastAPI application.

    The application's database dependency is overridden with the test session
    (``db_session``). ``pipeline_offer_page_playlists`` creates its own sessions via
    ``AsyncSessionFactory`` (bypassing the FastAPI dependency-injection layer) to
    support parallel execution — we patch that factory to use a session factory
    built on the test engine so those parallel tasks hit the testcontainer, not the
    production database.

    Because ``db_session`` now commits for real (see its docstring), any data seeded
    through it (e.g. via factories) is genuinely visible to the separate connections
    opened by ``test_async_session_factory`` below — unlike with an uncommitted,
    rolled-back outer transaction, which only the exact same physical connection can see.
    Isolation between tests is guaranteed by ``db_session``'s teardown, which truncates
    every table instead of rolling back.
    """

    async def override_get_database_session():
        yield db_session

    app.dependency_overrides[get_database_session] = override_get_database_session

    # Build a session factory that points at the *test* engine so that the parallel
    # tasks in pipeline_offer_page_playlists also use the testcontainer.
    test_async_session_factory = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False, autocommit=False, autoflush=False
    )

    with patch("controllers.pipeline_offer_page_playlists.AsyncSessionFactory", test_async_session_factory):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as async_client:
            yield async_client

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# VertexAPI
# ---------------------------------------------------------------------------


@pytest.fixture
def vertex_api():
    api = VertexAPI(endpoint_name="test-endpoint")
    api.vertex_infrastructure_service.execute_grpc_prediction = AsyncMock()
    return api


@pytest.fixture
def graph_vertex_api():
    api = VertexAPI(endpoint_name=settings.VERTEX_GRAPH_ENDPOINT_NAME)
    api.vertex_infrastructure_service.execute_grpc_prediction = AsyncMock()
    return api


# ---------------------------------------------------------------------------
# Redis integration fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def redis_container():
    """
    Start a Docker container running Redis for the test session.

    Yields the container instance so dependent fixtures can retrieve the connection URL.
    The container is automatically stopped once the session ends.
    """
    with RedisContainer() as redis:
        yield redis


@pytest_asyncio.fixture()
async def redis_service(redis_container):
    """
    Connect the global redis_cache_service singleton to the test Redis container.

    Yields the global singleton so:
    - Tests can call service methods directly.
    - RedisAPI (which imports redis_cache_service at module level) transparently
      hits the real container without any additional patching.
    Settings are restored after each test.
    """
    original_url = settings.REDIS_URL
    original_enabled = settings.REDIS_CACHE_ENABLED
    original_endpoint_cache = settings.ENDPOINT_RESPONSE_CACHE_ENABLED
    original_offer_resolution_cache = settings.OFFER_RESOLUTION_CACHE_ENABLED
    host = redis_container.get_container_host_ip()
    port = redis_container.get_exposed_port(6379)
    settings.REDIS_URL = f"redis://{host}:{port}"
    settings.REDIS_CACHE_ENABLED = True
    settings.ENDPOINT_RESPONSE_CACHE_ENABLED = True
    settings.OFFER_RESOLUTION_CACHE_ENABLED = True
    await redis_cache_service.connect()
    assert redis_cache_service.redis_client is not None
    await redis_cache_service.redis_client.flushall()
    yield redis_cache_service
    await redis_cache_service.disconnect()
    settings.REDIS_URL = original_url
    settings.REDIS_CACHE_ENABLED = original_enabled
    settings.ENDPOINT_RESPONSE_CACHE_ENABLED = original_endpoint_cache
    settings.OFFER_RESOLUTION_CACHE_ENABLED = original_offer_resolution_cache

import asyncio
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

import config.settings as _settings
from services.redis import RedisCacheService


# ---------------------------------------------------------------------------
# RedisCacheService.get_cached_value
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_returns_none_when_client_is_none(redis_service):
    """get_cached_value must return None immediately when no client is initialised."""
    service = RedisCacheService()  # redis_client is None from __init__

    result = await service.get_cached_value(cache_key="any-key")

    assert result is None


@pytest.mark.asyncio
async def test_get_returns_none_and_does_not_raise_on_redis_exception(redis_service):
    """Graceful degradation: a Redis failure must never crash the pipeline."""
    service = RedisCacheService()
    service.redis_client = redis_service.redis_client

    with patch.object(service.redis_client, "get", side_effect=Exception("Redis down")):
        result = await service.get_cached_value(cache_key="any-key")

    assert result is None


# ---------------------------------------------------------------------------
# RedisCacheService.set_cached_value
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_does_nothing_when_client_is_none(redis_service):
    """set_cached_value must be a no-op when no client is initialised."""
    service = RedisCacheService()  # redis_client is None from __init__

    await service.set_cached_value(cache_key="key", value_to_cache={"x": 1}, time_to_live_in_seconds=60)


@pytest.mark.asyncio
async def test_set_swallows_exception_without_raising(redis_service):
    """A Redis write failure must never crash the pipeline."""
    service = RedisCacheService()
    service.redis_client = redis_service.redis_client

    with patch.object(service.redis_client, "set", side_effect=Exception("Redis timeout")):
        await service.set_cached_value(cache_key="key", value_to_cache={}, time_to_live_in_seconds=60)


# ---------------------------------------------------------------------------
# RedisCacheService.connect
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_connect_does_nothing_when_cache_is_disabled(redis_service):
    """connect() must leave redis_client as None when REDIS_CACHE_ENABLED is False."""
    _settings.REDIS_CACHE_ENABLED = False  # redis_service fixture restores this on teardown
    service = RedisCacheService()
    await service.connect()

    assert service.redis_client is None


@pytest.mark.asyncio
async def test_connect_disables_cache_when_redis_url_is_empty(redis_service):
    """connect() must set redis_client to None and flip REDIS_CACHE_ENABLED to False when REDIS_URL is empty."""
    _settings.REDIS_URL = ""  # redis_service fixture restores this on teardown
    service = RedisCacheService()
    await service.connect()

    assert service.redis_client is None
    assert _settings.REDIS_CACHE_ENABLED is False


@pytest.mark.asyncio
async def test_connect_sets_live_client(redis_service):
    """connect() must set a live redis_client on success."""
    service = RedisCacheService()
    await service.connect()

    assert service.redis_client is not None
    await service.disconnect()


@pytest.mark.asyncio
async def test_connect_disables_cache_on_connection_failure(redis_service):
    """connect() must set redis_client to None and not raise when the Redis URL is unreachable."""
    _settings.REDIS_URL = "redis://localhost:1"  # port 1 is unreachable; redis_service restores on teardown
    service = RedisCacheService()
    await service.connect()

    assert service.redis_client is None


# ---------------------------------------------------------------------------
# RedisCacheService.get_cached_value / set_cached_value — round-trip
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_returns_value_stored_by_set(redis_service):
    """Round-trip: set then get must return the original dict."""
    await redis_service.set_cached_value(cache_key="rt-key", value_to_cache={"answer": 42}, time_to_live_in_seconds=60)

    result = await redis_service.get_cached_value(cache_key="rt-key")

    assert result == {"answer": 42}


@pytest.mark.asyncio
async def test_key_expires_after_ttl(redis_service):
    """A key stored with TTL=1 must not be retrievable after 2 seconds."""
    await redis_service.set_cached_value(cache_key="ttl-key", value_to_cache={"x": 1}, time_to_live_in_seconds=1)

    await asyncio.sleep(2)

    result = await redis_service.get_cached_value(cache_key="ttl-key")

    assert result is None


@pytest.mark.asyncio
async def test_get_returns_none_for_missing_key(redis_service):
    """get_cached_value must return None for a key that was never written."""
    result = await redis_service.get_cached_value(cache_key="never-written-key-xyz")

    assert result is None


# ---------------------------------------------------------------------------
# RedisCacheService.disconnect — connection teardown
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_disconnect_closes_connection(redis_service):
    """After disconnect(), the redis_client must be closeable without error."""
    service = RedisCacheService()
    await service.connect()
    assert service.redis_client is not None

    await service.disconnect()


# ---------------------------------------------------------------------------
# RedisCacheService — timeout behaviour
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_cached_value_returns_none_on_timeout(redis_service):
    """get_cached_value must return None and log a warning when Redis exceeds the configured timeout."""
    service = RedisCacheService()
    service.redis_client = redis_service.redis_client

    async def slow_get(*args, **kwargs):
        await asyncio.sleep(10)

    with (
        patch.object(service.redis_client, "get", side_effect=slow_get),
        patch("services.redis.logger") as mock_logger,
        patch.object(_settings, "REDIS_TIMEOUT_SECONDS", 0.05),
    ):
        result = await service.get_cached_value(cache_key="slow-key")

    assert result is None
    mock_logger.warning.assert_called_once()
    warning_call_kwargs = mock_logger.warning.call_args
    assert "timeout" in warning_call_kwargs[0][0].lower()


@pytest.mark.asyncio
async def test_set_cached_value_swallows_timeout(redis_service):
    """set_cached_value must not raise and must log a warning when Redis exceeds the timeout."""
    service = RedisCacheService()
    service.redis_client = redis_service.redis_client

    async def slow_set(*args, **kwargs):
        await asyncio.sleep(10)

    with (
        patch.object(service.redis_client, "set", side_effect=slow_set),
        patch("services.redis.logger") as mock_logger,
        patch.object(_settings, "REDIS_TIMEOUT_SECONDS", 0.05),
    ):
        await service.set_cached_value(cache_key="slow-key", value_to_cache={"x": 1}, time_to_live_in_seconds=60)

    mock_logger.warning.assert_called_once()
    assert "timeout" in mock_logger.warning.call_args[0][0].lower()


@pytest.mark.asyncio
async def test_mget_cached_values_returns_all_none_on_timeout(redis_service):
    """mget_cached_values must return a list of None values and log a warning on timeout."""
    service = RedisCacheService()
    service.redis_client = redis_service.redis_client

    async def slow_mget(*args, **kwargs):
        await asyncio.sleep(10)

    with (
        patch.object(service.redis_client, "mget", side_effect=slow_mget),
        patch("services.redis.logger") as mock_logger,
        patch.object(_settings, "REDIS_TIMEOUT_SECONDS", 0.05),
    ):
        result = await service.mget_cached_values(cache_keys=["k1", "k2", "k3"])

    assert result == [None, None, None]
    mock_logger.warning.assert_called_once()
    assert "timeout" in mock_logger.warning.call_args[0][0].lower()


@pytest.mark.asyncio
async def test_mset_cached_values_swallows_timeout(redis_service):
    """mset_cached_values must not raise and must log a warning when the pipeline execute() exceeds the timeout."""
    service = RedisCacheService()
    service.redis_client = redis_service.redis_client

    async def slow_execute(*args, **kwargs):
        await asyncio.sleep(10)

    # Patch the pipeline's execute coroutine to simulate a slow Redis response.
    mock_pipe = AsyncMock()
    mock_pipe.__aenter__ = AsyncMock(return_value=mock_pipe)
    mock_pipe.__aexit__ = AsyncMock(return_value=False)
    mock_pipe.set = MagicMock()
    mock_pipe.execute = slow_execute

    with (
        patch.object(service.redis_client, "pipeline", return_value=mock_pipe),
        patch("services.redis.logger") as mock_logger,
        patch.object(_settings, "REDIS_TIMEOUT_SECONDS", 0.05),
    ):
        await service.mset_cached_values(key_value_pairs={"k1": {"a": 1}, "k2": {"b": 2}}, time_to_live_in_seconds=60)

    mock_logger.warning.assert_called_once()
    assert "timeout" in mock_logger.warning.call_args[0][0].lower()

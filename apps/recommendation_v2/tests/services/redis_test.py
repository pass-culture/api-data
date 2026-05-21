import asyncio
import json

import pytest

import config.settings as _settings
from services.redis import RedisCacheService


# ---------------------------------------------------------------------------
# RedisCacheService.get_cached_value
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_returns_none_when_client_is_none():
    service = RedisCacheService()
    service.redis_client = None

    result = await service.get_cached_value(cache_key="any-key")

    assert result is None


@pytest.mark.asyncio
async def test_get_returns_deserialized_value_when_key_exists(mocker):
    service = RedisCacheService()
    service.redis_client = mocker.AsyncMock()
    stored = {"offer_id": "offer-1", "score": 0.9}
    service.redis_client.get.return_value = json.dumps(stored)

    result = await service.get_cached_value(cache_key="existing-key")

    assert result == stored


@pytest.mark.asyncio
async def test_get_returns_none_when_key_not_found(mocker):
    service = RedisCacheService()
    service.redis_client = mocker.AsyncMock()
    service.redis_client.get.return_value = None

    result = await service.get_cached_value(cache_key="missing-key")

    assert result is None


@pytest.mark.asyncio
async def test_get_returns_none_and_does_not_raise_on_redis_exception(mocker):
    """Graceful degradation: a Redis failure must never crash the pipeline."""
    service = RedisCacheService()
    service.redis_client = mocker.AsyncMock()
    service.redis_client.get.side_effect = Exception("Redis down")

    result = await service.get_cached_value(cache_key="any-key")

    assert result is None


# ---------------------------------------------------------------------------
# RedisCacheService.set_cached_value
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_does_nothing_when_client_is_none():
    service = RedisCacheService()
    service.redis_client = None

    await service.set_cached_value(cache_key="key", value_to_cache={"x": 1}, time_to_live_in_seconds=60)


@pytest.mark.asyncio
async def test_set_serializes_value_and_calls_redis_set_with_ttl(mocker):
    service = RedisCacheService()
    service.redis_client = mocker.AsyncMock()
    value = {"offer_id": "offer-1"}

    await service.set_cached_value(cache_key="my-key", value_to_cache=value, time_to_live_in_seconds=3600)

    service.redis_client.set.assert_called_once_with(
        name="my-key",
        value=json.dumps(value),
        ex=3600,
    )


@pytest.mark.asyncio
async def test_set_swallows_exception_without_raising(mocker):
    """A Redis write failure must never crash the pipeline."""
    service = RedisCacheService()
    service.redis_client = mocker.AsyncMock()
    service.redis_client.set.side_effect = Exception("Redis timeout")

    await service.set_cached_value(cache_key="key", value_to_cache={}, time_to_live_in_seconds=60)


# ---------------------------------------------------------------------------
# RedisCacheService.connect
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_connect_does_nothing_when_cache_is_disabled(mocker):
    mocker.patch.object(_settings, "REDIS_CACHE_ENABLED", new=False)
    mock_redis = mocker.patch("services.redis.redis")

    service = RedisCacheService()
    await service.connect()

    assert service.redis_client is None
    mock_redis.Redis.from_url.assert_not_called()


@pytest.mark.asyncio
async def test_connect_disables_cache_when_redis_url_is_empty(mocker):
    mocker.patch.object(_settings, "REDIS_CACHE_ENABLED", new=True)
    mocker.patch.object(_settings, "REDIS_URL", new="")

    service = RedisCacheService()
    await service.connect()

    assert service.redis_client is None
    assert _settings.REDIS_CACHE_ENABLED is False


@pytest.mark.asyncio
async def test_connect_creates_client_and_starts_monitor_when_ping_succeeds(mocker):
    mocker.patch.object(_settings, "REDIS_CACHE_ENABLED", new=True)
    mocker.patch.object(_settings, "REDIS_URL", new="redis://localhost:6379/0")

    mock_client = mocker.MagicMock()
    mock_client.ping.return_value = True
    mocker.patch("services.redis.redis").Redis.from_url.return_value = mock_client

    service = RedisCacheService()
    # Patch the method on the instance so asyncio.create_task receives a coroutine
    # that completes immediately — avoids the "coroutine never awaited" ResourceWarning.
    mocker.patch.object(service, "_monitor_connections", new_callable=mocker.AsyncMock)
    await service.connect()

    assert service.redis_client is mock_client
    assert service._monitor_task is not None


@pytest.mark.asyncio
async def test_connect_disables_cache_on_connection_error(mocker):
    """
    Verifies that a Redis connection failure during startup disables the cache gracefully.

    If ping() raises, the service must set redis_client to None, flip REDIS_CACHE_ENABLED
    to False, and not propagate the exception — allowing the API to start without cache.
    """
    mocker.patch.object(_settings, "REDIS_CACHE_ENABLED", new=True)
    mocker.patch.object(_settings, "REDIS_URL", new="redis://localhost:6379/0")

    mock_client = mocker.MagicMock()
    mock_client.ping.side_effect = Exception("Connection refused")
    mocker.patch("services.redis.redis").Redis.from_url.return_value = mock_client

    service = RedisCacheService()
    await service.connect()

    assert service.redis_client is None
    assert _settings.REDIS_CACHE_ENABLED is False


# ---------------------------------------------------------------------------
# RedisCacheService.disconnect
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_disconnect_cancels_and_clears_monitor_task():
    """
    Verifies that an active background monitor task is cancelled and the reference cleared.

    A real asyncio Task is used so the cancel/await interaction is exercised without mocking
    asyncio internals.
    """
    service = RedisCacheService()

    async def _run_forever():
        while True:
            await asyncio.sleep(1000)

    task = asyncio.create_task(_run_forever())
    service._monitor_task = task

    await service.disconnect()

    assert service._monitor_task is None
    assert task.cancelled()


@pytest.mark.asyncio
async def test_disconnect_calls_aclose_on_redis_client(mocker):
    service = RedisCacheService()
    mock_client = mocker.AsyncMock()
    service.redis_client = mock_client

    await service.disconnect()

    mock_client.aclose.assert_called_once()


@pytest.mark.asyncio
async def test_disconnect_falls_back_to_close_when_aclose_raises_attribute_error(mocker):
    """
    Verifies the compatibility fallback for older redis-py versions that lack aclose().

    When aclose() raises AttributeError the service must silently retry with close()
    and not propagate any exception.
    """
    service = RedisCacheService()
    mock_client = mocker.AsyncMock()
    mock_client.aclose.side_effect = AttributeError("no aclose")
    service.redis_client = mock_client

    await service.disconnect()  # must not raise

    mock_client.close.assert_called_once()


@pytest.mark.asyncio
async def test_disconnect_logs_warning_and_does_not_raise_on_aclose_exception(mocker):
    """A failure to close the Redis connection must be logged but must never crash the shutdown path."""
    service = RedisCacheService()
    mock_client = mocker.AsyncMock()
    mock_client.aclose.side_effect = Exception("socket hang up")
    service.redis_client = mock_client

    mock_logger = mocker.patch("services.redis.logger")

    await service.disconnect()  # must not raise

    mock_logger.warning.assert_called_once()


# ---------------------------------------------------------------------------
# RedisCacheService._monitor_connections
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_monitor_connections_logs_connected_clients_count(mocker):
    """
    Verifies that the monitor loop queries Redis for client metrics and logs the result.

    asyncio.sleep is replaced with a CancelledError to exit the infinite loop after
    exactly one iteration without hanging the test suite.
    """
    service = RedisCacheService()
    service.redis_client = mocker.AsyncMock()
    service.redis_client.info.return_value = {"connected_clients": 7}

    mock_logger = mocker.patch("services.redis.logger")
    mocker.patch("asyncio.sleep", side_effect=asyncio.CancelledError)

    with pytest.raises(asyncio.CancelledError):
        await service._monitor_connections()

    service.redis_client.info.assert_called_once_with(section="clients")
    mock_logger.info.assert_called_once()


@pytest.mark.asyncio
async def test_monitor_connections_logs_debug_and_does_not_crash_on_info_error(mocker):
    """
    Verifies that an exception from redis_client.info() is swallowed and logged at DEBUG level.

    The loop must survive the error — only the CancelledError from the mocked sleep
    terminates the coroutine in this test.
    """
    service = RedisCacheService()
    service.redis_client = mocker.AsyncMock()
    service.redis_client.info.side_effect = Exception("Redis unavailable")

    mock_logger = mocker.patch("services.redis.logger")
    mocker.patch("asyncio.sleep", side_effect=asyncio.CancelledError)

    with pytest.raises(asyncio.CancelledError):
        await service._monitor_connections()

    mock_logger.debug.assert_called_once()
    mock_logger.info.assert_not_called()

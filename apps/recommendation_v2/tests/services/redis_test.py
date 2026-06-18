import asyncio
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
async def test_connect_sets_live_client_and_starts_monitor(redis_service):
    """connect() must set a live redis_client and start the background monitor task on success."""
    service = RedisCacheService()
    await service.connect()

    assert service.redis_client is not None
    assert service._monitor_task is not None
    await service.disconnect()


@pytest.mark.asyncio
async def test_connect_disables_cache_on_connection_failure(redis_service):
    """connect() must set redis_client to None and not raise when the Redis URL is unreachable."""
    _settings.REDIS_URL = "redis://localhost:1"  # port 1 is unreachable; redis_service restores on teardown
    service = RedisCacheService()
    await service.connect()

    assert service.redis_client is None


# ---------------------------------------------------------------------------
# RedisCacheService.disconnect
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_disconnect_cancels_and_clears_monitor_task(redis_service):
    """
    disconnect() must cancel the background monitor task and set the reference to None.

    The 0.1 s sleep lets the background task created by redis_service.connect() complete
    its first iteration before we call disconnect(), so the task is in its 60 s sleep and
    cancel() hits a predictable await point. The task reference is saved before disconnect()
    clears it so we can assert task.cancelled() afterward.
    """
    await asyncio.sleep(0.1)  # let the background task complete its first iteration
    task = redis_service._monitor_task  # save reference before disconnect clears it

    await redis_service.disconnect()

    assert redis_service._monitor_task is None
    assert task.cancelled()


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
# RedisCacheService._monitor_connections
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_monitor_connections_logs_connected_clients_count(redis_service):
    """
    The monitor loop must query Redis for client metrics and log the result at INFO level.

    A fresh service shares the real client but has no background task of its own, so only
    one coroutine calls logger.info inside the test window.

    asyncio.create_task() in connect() schedules the fixture's background task but does not
    run it — it fires on the next event-loop tick. The 0.1 s sleep yields control so the
    task runs its redis_client.info() + logger.info() cycle (with the real logger, before
    our mock) and then suspends on asyncio.sleep(60). It cannot interfere during our 0.5 s
    window.

    wait_for then drives service._monitor_connections() through one info+log cycle, the loop
    hits asyncio.sleep(60), and the 0.5 s timeout fires — TimeoutError is expected.
    """
    service = RedisCacheService()
    service.redis_client = redis_service.redis_client

    # Let the fixture's background task complete its first iteration before we apply the mock.
    await asyncio.sleep(0.1)

    # The fixture's background task has acquired the distributed lock. Delete it so the
    # service under test can acquire it and actually log the metrics.
    await redis_service.redis_client.delete("redis_monitor_leader_lock")

    with patch("services.redis.logger") as mock_logger, pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(service._monitor_connections(), timeout=0.5)

    mock_logger.info.assert_called_once()


@pytest.mark.asyncio
async def test_monitor_connections_logs_debug_and_does_not_crash_on_info_error(redis_service):
    """
    An exception from redis_client.info() must be swallowed and logged at DEBUG level.

    Same pattern as test_monitor_connections_logs_connected_clients_count: the 0.1 s sleep
    lets the fixture's background task run its info+log cycle and suspend on asyncio.sleep(60)
    before the mock is applied. patch.object then injects a failure on the specific client
    instance shared with the fresh service, so the monitor loop catches the exception and
    logs at DEBUG instead of INFO.
    """
    service = RedisCacheService()
    service.redis_client = redis_service.redis_client

    # yield to the event loop so the fixture's background task runs its info+log cycle and suspends on asyncio.sleep(60)
    await asyncio.sleep(0.1)

    # The fixture's background task has acquired the distributed lock. Delete it so the
    # service under test can acquire it and trigger the info() call (which will raise).
    await redis_service.redis_client.delete("redis_monitor_leader_lock")

    with (
        patch.object(service.redis_client, "info", side_effect=Exception("Redis unavailable")),
        patch("services.redis.logger") as mock_logger,
        pytest.raises(asyncio.TimeoutError),
    ):
        await asyncio.wait_for(service._monitor_connections(), timeout=0.5)

    mock_logger.debug.assert_called_once()
    mock_logger.info.assert_not_called()


# ---------------------------------------------------------------------------
# RedisCacheService.disconnect — connection teardown
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_disconnect_closes_connection(redis_service):
    """After disconnect(), the monitor task reference must be cleared."""
    service = RedisCacheService()
    await service.connect()
    assert service.redis_client is not None

    await service.disconnect()

    assert service._monitor_task is None

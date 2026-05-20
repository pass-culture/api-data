import json

import pytest

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

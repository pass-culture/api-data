from datetime import UTC
from datetime import datetime
from datetime import time
from datetime import timedelta

import pytest

import config.settings as _settings
from connectors.redis_api import RedisAPI
from schemas.playlist_recommendation import RecommendationMetadata
from schemas.playlist_recommendation import RecommendationResponse

from tests.factories.schemas import RecommendationResponseFactory


_MD5_HEX_LENGTH = 32


# Hardcoded in tests so assertions are exact known values, not re-derived from settings
_TEST_RESET_HOUR = 5
_SECONDS_PER_DAY = 86400

_TTL_BOUNDARY_CASES = [
    pytest.param(datetime(2024, 6, 15, 4, 59, 59, tzinfo=UTC), 1, id="one_second_before_reset"),
    pytest.param(datetime(2024, 6, 15, 5, 0, 0, tzinfo=UTC), _SECONDS_PER_DAY, id="exactly_at_reset_rolls_over"),
    pytest.param(datetime(2024, 6, 15, 5, 0, 1, tzinfo=UTC), _SECONDS_PER_DAY - 1, id="one_second_after_reset"),
    pytest.param(datetime(2024, 6, 15, 0, 0, 0, tzinfo=UTC), 18000, id="midnight_five_hours_out"),
]


# ---------------------------------------------------------------------------
# RedisAPI.generate_cache_key
# ---------------------------------------------------------------------------


def test_generate_cache_key_is_deterministic():
    key1 = RedisAPI.generate_cache_key("ns", {"a": 1, "b": 2})
    key2 = RedisAPI.generate_cache_key("ns", {"a": 1, "b": 2})
    assert key1 == key2


def test_generate_cache_key_differs_for_different_signatures():
    key_a = RedisAPI.generate_cache_key("ns", {"user_id": "user-A"})
    key_b = RedisAPI.generate_cache_key("ns", {"user_id": "user-B"})
    assert key_a != key_b


def test_generate_cache_key_treats_none_and_string_as_distinct():
    key_none = RedisAPI.generate_cache_key("ns", {"user_id": None})
    key_value = RedisAPI.generate_cache_key("ns", {"user_id": "x"})
    assert key_none != key_value


def test_generate_cache_key_yields_same_key_for_different_signature_orders():
    key1 = RedisAPI.generate_cache_key("ns", {"a": 1, "b": 2})
    key2 = RedisAPI.generate_cache_key("ns", {"b": 2, "a": 1})
    assert key1 == key2


def test_generate_cache_key_yields_same_key_for_nested_signature_with_different_orders():
    key1 = RedisAPI.generate_cache_key("ns", {"a": 1, "b": 2, "c": {"key1": "value1", "key2": "value2"}})
    key2 = RedisAPI.generate_cache_key("ns", {"b": 2, "c": {"key2": "value2", "key1": "value1"}, "a": 1})
    assert key1 == key2


def test_generate_cache_key_format_is_namespace_colon_hash():
    key = RedisAPI.generate_cache_key("playlist_recommendation", {"user_id": "x"})
    namespace, hash_part = key.split(":", 1)
    assert namespace == "playlist_recommendation"
    assert len(hash_part) == _MD5_HEX_LENGTH  # sligthly pointless since hashlib is probably extensively tested


# ---------------------------------------------------------------------------
# RedisAPI.calculate_seconds_until_next_database_population_time
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("frozen_now", "expected_ttl"), _TTL_BOUNDARY_CASES)
def test_ttl_boundary_cases(mocker, frozen_now, expected_ttl):
    """
    Boundary conditions around the reset hour at 05:00:00 UTC:
    - one second before  → TTL = 1 s (same day, no rollover)
    - exactly at reset   → TTL = 86400 s (rolls over to next day)
    - one second after   → TTL = 86399 s (next day, minus the elapsed second)
    - midnight           → TTL = 18000 s (5 h until reset)
    """
    mocker.patch.object(_settings, "REDIS_CACHE_RESET_HOUR", new=_TEST_RESET_HOUR)
    mock_dt = mocker.patch("connectors.redis_api.datetime")
    mock_dt.now.return_value = frozen_now
    mock_dt.combine.side_effect = datetime.combine

    ttl = RedisAPI.calculate_seconds_until_next_database_population_time()

    assert ttl == expected_ttl


def test_ttl_points_to_the_next_reset_hour():
    now = datetime.now(UTC)
    ttl = RedisAPI.calculate_seconds_until_next_database_population_time()
    cache_expiry = now + timedelta(seconds=ttl)

    reset_hour = _settings.REDIS_CACHE_RESET_HOUR
    next_population_at = datetime.combine(now.date(), time(reset_hour, 0), UTC)
    if now >= next_population_at:
        next_population_at += timedelta(days=1)

    assert (
        abs((cache_expiry - next_population_at).total_seconds()) < 1
    )  # allow 1 second of execution time between calculation and assertion


# ---------------------------------------------------------------------------
# RedisAPI.fetch_cached_response
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_returns_none_when_cache_disabled(mocker):
    mocker.patch.object(_settings, "REDIS_CACHE_ENABLED", new=False)
    mock_get = mocker.patch(
        "connectors.redis_api.redis_cache_service.get_cached_value",
        new_callable=mocker.AsyncMock,
    )

    result = await RedisAPI.fetch_cached_response(
        namespace_prefix="ns",
        request_signature_data={"user_id": "x"},
        response_model_class=RecommendationResponse,
    )

    assert result is None
    mock_get.assert_not_called()


@pytest.mark.asyncio
async def test_fetch_returns_instantiated_model_on_hit(mocker):
    cached_dict = RecommendationResponse(
        playlist_recommended_offers=["offer-1"],
        params=RecommendationMetadata(reco_origin="home", model_origin="default", call_id="call-1"),
        from_cache=False,
    ).model_dump(mode="json")

    mocker.patch.object(_settings, "REDIS_CACHE_ENABLED", new=True)
    mocker.patch(
        "connectors.redis_api.redis_cache_service.get_cached_value",
        new_callable=mocker.AsyncMock,
        return_value=cached_dict,
    )

    result = await RedisAPI.fetch_cached_response(
        namespace_prefix="playlist_recommendation",
        request_signature_data={"user_id": "x"},
        response_model_class=RecommendationResponse,
    )

    assert isinstance(result, RecommendationResponse)
    assert result.playlist_recommended_offers == ["offer-1"]


@pytest.mark.asyncio
async def test_fetch_returns_none_on_miss(mocker):
    mocker.patch.object(_settings, "REDIS_CACHE_ENABLED", new=True)
    mocker.patch(
        "connectors.redis_api.redis_cache_service.get_cached_value",
        new_callable=mocker.AsyncMock,
        return_value=None,
    )

    result = await RedisAPI.fetch_cached_response(
        namespace_prefix="ns",
        request_signature_data={"user_id": "x"},
        response_model_class=RecommendationResponse,
    )

    assert result is None


# ---------------------------------------------------------------------------
# RedisAPI.store_endpoint_response
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_store_does_nothing_when_cache_disabled(mocker):
    mocker.patch.object(_settings, "REDIS_CACHE_ENABLED", new=False)
    mock_set = mocker.patch(
        "connectors.redis_api.redis_cache_service.set_cached_value",
        new_callable=mocker.AsyncMock,
    )

    await RedisAPI.store_endpoint_response(
        namespace_prefix="ns",
        request_signature_data={"user_id": "x"},
        response_model_instance=RecommendationResponse(
            playlist_recommended_offers=[],
            params=RecommendationMetadata(reco_origin="algo", model_origin="default", call_id="call-1"),
            from_cache=False,
        ),
    )

    mock_set.assert_not_called()


@pytest.mark.asyncio
async def test_store_calls_set_with_serialized_payload_and_ttl(mocker):
    mocker.patch.object(_settings, "REDIS_CACHE_ENABLED", new=True)
    mock_set = mocker.patch(
        "connectors.redis_api.redis_cache_service.set_cached_value",
        new_callable=mocker.AsyncMock,
    )
    model = RecommendationResponse(
        playlist_recommended_offers=["offer-1"],
        params=RecommendationMetadata(reco_origin="algo", model_origin="default", call_id="call-1"),
        from_cache=False,
    )

    await RedisAPI.store_endpoint_response(
        namespace_prefix="playlist_recommendation",
        request_signature_data={"user_id": "x"},
        response_model_instance=model,
    )

    mock_set.assert_called_once()
    kwargs = mock_set.call_args.kwargs
    assert kwargs["cache_key"] == RedisAPI.generate_cache_key("playlist_recommendation", {"user_id": "x"})
    assert kwargs["value_to_cache"] == model.model_dump(mode="json")
    assert isinstance(kwargs["time_to_live_in_seconds"], int)
    assert kwargs["time_to_live_in_seconds"] > 0


# ---------------------------------------------------------------------------
# Integration tests — require a live Redis container (redis_service fixture)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_store_then_fetch_returns_original_model(redis_service):
    """A response stored via store_endpoint_response must be returned verbatim by fetch_cached_response."""
    model = RecommendationResponseFactory.build()
    sig = {"user_id": "integration-user-1"}

    await RedisAPI.store_endpoint_response(
        namespace_prefix="playlist_recommendation",
        request_signature_data=sig,
        response_model_instance=model,
    )
    result = await RedisAPI.fetch_cached_response(
        namespace_prefix="playlist_recommendation",
        request_signature_data=sig,
        response_model_class=RecommendationResponse,
    )

    assert isinstance(result, RecommendationResponse)
    assert result.playlist_recommended_offers == model.playlist_recommended_offers


@pytest.mark.asyncio
async def test_different_namespace_returns_none(redis_service):
    """A cache entry stored under namespace 'ns-a' must not be retrievable under 'ns-b'."""
    sig = {"user_id": "ns-test-user"}

    await RedisAPI.store_endpoint_response(
        namespace_prefix="ns-a",
        request_signature_data=sig,
        response_model_instance=RecommendationResponseFactory.build(),
    )
    result = await RedisAPI.fetch_cached_response(
        namespace_prefix="ns-b",
        request_signature_data=sig,
        response_model_class=RecommendationResponse,
    )

    assert result is None


@pytest.mark.asyncio
async def test_different_signature_returns_none(redis_service):
    """A cache entry keyed on user-A must not be returned when querying for user-B."""
    sig_a = {"user_id": "user-A"}
    sig_b = {"user_id": "user-B"}

    await RedisAPI.store_endpoint_response(
        namespace_prefix="playlist_recommendation",
        request_signature_data=sig_a,
        response_model_instance=RecommendationResponseFactory.build(),
    )
    result = await RedisAPI.fetch_cached_response(
        namespace_prefix="playlist_recommendation",
        request_signature_data=sig_b,
        response_model_class=RecommendationResponse,
    )

    assert result is None


@pytest.mark.asyncio
async def test_different_signatures_produce_independent_cache_entries(redis_service):
    """Two distinct signatures must produce independent cache entries without cross-contamination."""
    sig_a = {"offer_id": "offer-1", "user_id": "user-A"}
    sig_b = {"offer_id": "offer-1", "user_id": "user-B"}
    model_a = RecommendationResponseFactory.build()
    model_b = RecommendationResponseFactory.build()

    await RedisAPI.store_endpoint_response("similar_offer", sig_a, model_a)
    await RedisAPI.store_endpoint_response("similar_offer", sig_b, model_b)

    result_a = await RedisAPI.fetch_cached_response("similar_offer", sig_a, RecommendationResponse)
    result_b = await RedisAPI.fetch_cached_response("similar_offer", sig_b, RecommendationResponse)

    assert result_a.playlist_recommended_offers == model_a.playlist_recommended_offers
    assert result_b.playlist_recommended_offers == model_b.playlist_recommended_offers

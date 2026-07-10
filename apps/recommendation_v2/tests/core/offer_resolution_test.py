from types import SimpleNamespace
from unittest.mock import AsyncMock
from unittest.mock import MagicMock

import pytest

from connectors.redis_api import RedisAPI
from core.geo import MAX_DISTANCE_METERS_FOR_OFFER_RETRIEVAL
from core.offer_resolution import _resolve_multi_venue_items
from core.offer_resolution import resolve_closest_venues_from_items
from core.user_context import UserContext
from schemas.vertex_prediction_item import ItemOrigin

from tests.conftest import patch_all_caches_disabled
from tests.conftest import patch_all_caches_enabled
from tests.factories.schemas import RecommendableItemFactory
from tests.factories.schemas import UserContextFactory


# ---------------------------------------------------------------------------
# resolve_closest_venues_from_items
# ---------------------------------------------------------------------------

_PARIS = (48.8566, 2.3522)
_VERSAILLES = (48.8048, 2.1203)  # ~17 km from Paris
_LONDON = (51.5074, -0.1278)  # ~343 km from Paris
_MOCK_TTL_SECONDS = 3600


@pytest.mark.asyncio
async def test_resolve_returns_empty_for_empty_input(db_session):
    result = await resolve_closest_venues_from_items(db_session, [], UserContextFactory.build())
    assert result == []


@pytest.mark.asyncio
async def test_resolve_fast_tracks_digital_item_without_computing_distance(db_session):
    """Digital (non-geolocated) items bypass the DB and are returned with no distance."""
    user = UserContext(user_id="u", latitude=_PARIS[0], longitude=_PARIS[1])
    item = RecommendableItemFactory.build(is_geolocated=False, total_offers=10)

    result = await resolve_closest_venues_from_items(db_session, [item], user)

    assert len(result) == 1
    assert result[0].offer_user_distance is None


@pytest.mark.asyncio
async def test_resolve_computes_distance_for_single_venue_geolocated_item(db_session):
    """Single-venue physical items are fast-tracked but their distance from the user is computed via haversine."""
    user = UserContext(user_id="u", latitude=_PARIS[0], longitude=_PARIS[1])
    item = RecommendableItemFactory.build(
        is_geolocated=True,
        total_offers=1,
        example_venue_latitude=_VERSAILLES[0],
        example_venue_longitude=_VERSAILLES[1],
    )

    max_distance_meters = 50_000
    result = await resolve_closest_venues_from_items(db_session, [item], user)

    assert len(result) == 1
    assert result[0].offer_user_distance is not None
    assert result[0].offer_user_distance < max_distance_meters


@pytest.mark.asyncio
async def test_resolve_skips_geolocated_item_when_user_has_no_gps(db_session):
    """A geolocated single-venue item is silently dropped when the user has no GPS coordinates."""
    user = UserContext(user_id="u")  # no GPS
    item = RecommendableItemFactory.build(is_geolocated=True, total_offers=1)

    result = await resolve_closest_venues_from_items(db_session, [item], user)

    assert result == []


@pytest.mark.asyncio
async def test_resolve_skips_item_beyond_100km(db_session):
    """Items whose closest venue exceeds the 100 km radius are excluded regardless of relevance score."""
    user = UserContext(user_id="u", latitude=_PARIS[0], longitude=_PARIS[1])
    item = RecommendableItemFactory.build(
        is_geolocated=True,
        total_offers=1,
        example_venue_latitude=_LONDON[0],
        example_venue_longitude=_LONDON[1],
    )

    result = await resolve_closest_venues_from_items(db_session, [item], user)

    assert result == []


@pytest.mark.asyncio
async def test_resolve_drops_multi_venue_item_when_user_has_no_gps(db_session):
    """
    Multi-venue items are only routed to the DB query when the user is geolocated;
    without GPS they are silently dropped.
    """
    user = UserContext(user_id="u")  # no GPS
    item = RecommendableItemFactory.build(is_geolocated=True, total_offers=5)

    result = await resolve_closest_venues_from_items(db_session, [item], user)

    assert result == []


@pytest.mark.asyncio
async def test_resolve_sorts_offers_by_distance_with_none_last(db_session):
    """
    The final list is sorted ascending by distance;
    offers with no distance (digital items) are treated as inf and sorted last.

    Mixing geolocated and digital items in the input validates both the sort key and the None-last sentinel.
    """
    user = UserContext(user_id="u", latitude=_PARIS[0], longitude=_PARIS[1])

    near_item = RecommendableItemFactory.build(
        is_geolocated=True,
        total_offers=1,
        example_venue_latitude=_VERSAILLES[0],
        example_venue_longitude=_VERSAILLES[1],
    )
    far_item = RecommendableItemFactory.build(
        is_geolocated=True,
        total_offers=1,
        example_venue_latitude=48.0,
        example_venue_longitude=1.0,
    )
    digital_item = RecommendableItemFactory.build(is_geolocated=False)

    result = await resolve_closest_venues_from_items(db_session, [far_item, near_item, digital_item], user)

    distances = [r.offer_user_distance for r in result]
    non_none = [d for d in distances if d is not None]
    assert non_none == sorted(non_none)
    assert distances[-1] is None


# ---------------------------------------------------------------------------
# _resolve_multi_venue_items — Cache strategy
#
# These unit tests exercise the offer-resolution cache logic in isolation by
# mocking Redis (mget / mset) and the spatial DB query. No real DB or Redis
# container is needed.
#
# Cache rules under test:
#   - Only "tops" items are eligible for caching (USER_BASED / GRAPH always hit DB).
#   - When OFFER_RESOLUTION_CACHE_ENABLED=False → mget is never called.
#   - Cache HIT   → enriched offer built from cached payload, DB query skipped.
#   - Cache MISS  → DB query executed, result written back to cache via mset.
#   - Cache HIT whose venue exceeds MAX_DISTANCE_METERS_FOR_OFFER_RETRIEVAL → dropped.
#   - Partial hit  → only cache-miss items are sent to DB.
#   - DB does not resolve an item (no venue found) → mset is not called for that item.
# ---------------------------------------------------------------------------


def _make_db_row(
    item_id: str,
    offer_id: str = "offer-db",
    lat: float = _VERSAILLES[0],
    lng: float = _VERSAILLES[1],
    distance: float = 17_000.0,
) -> tuple:
    """Builds a fake (db_offer, distance) tuple as returned by find_closest_offers_with_h3_index."""
    db_offer = SimpleNamespace(
        item_id=item_id,
        offer_id=offer_id,
        venue_latitude=lat,
        venue_longitude=lng,
        offer_creation_date=None,
        stock_beginning_date=None,
    )
    return (db_offer, distance)


def _make_cached_payload(
    offer_id: str = "offer-cached",
    lat: float = _VERSAILLES[0],
    lng: float = _VERSAILLES[1],
) -> dict:
    """Builds a minimal offer-resolution cache payload dict."""
    return {
        "offer_id": offer_id,
        "venue_latitude": lat,
        "venue_longitude": lng,
        "offer_creation_date": None,
        "stock_beginning_date": None,
    }


@pytest.mark.asyncio
async def test_cache_disabled_skips_mget_for_tops_items(mocker):
    """
    When OFFER_RESOLUTION_CACHE_ENABLED=False, the Redis MGET round-trip is never
    initiated even when all items are eligible tops items.
    """
    patch_all_caches_disabled(mocker)
    mock_mget = mocker.patch("core.offer_resolution.redis_api.mget_resolved_offers", new_callable=AsyncMock)
    mocker.patch("core.offer_resolution.find_closest_offers_with_h3_index", new_callable=AsyncMock, return_value=[])

    user = UserContext(user_id="u", latitude=_PARIS[0], longitude=_PARIS[1])
    item = RecommendableItemFactory.build(item_origin=ItemOrigin.TOPS, is_geolocated=True, total_offers=5)
    item_lookup_map = {item.item_id: item}

    await _resolve_multi_venue_items(MagicMock(), [item.item_id], item_lookup_map, user)

    mock_mget.assert_not_called()


@pytest.mark.asyncio
async def test_cache_hit_for_tops_item_skips_db_query(mocker):
    """
    A full cache hit for a tops item means the spatial DB query is never executed
    and the enriched offer is built directly from the cached payload.
    """
    patch_all_caches_enabled(mocker)
    mocker.patch("core.offer_resolution.get_h3_index_from_coordinates", return_value="fake-h3-cell")
    mocker.patch(
        "core.offer_resolution.redis_api.mget_resolved_offers",
        new_callable=AsyncMock,
        return_value=[_make_cached_payload(offer_id="offer-from-cache")],
    )
    mock_db_query = mocker.patch(
        "core.offer_resolution.find_closest_offers_with_h3_index", new_callable=AsyncMock, return_value=[]
    )

    user = UserContext(user_id="u", latitude=_PARIS[0], longitude=_PARIS[1])
    item = RecommendableItemFactory.build(item_origin=ItemOrigin.TOPS, is_geolocated=True, total_offers=5)
    item_lookup_map = {item.item_id: item}

    result = await _resolve_multi_venue_items(MagicMock(), [item.item_id], item_lookup_map, user)

    mock_db_query.assert_not_called()
    assert len(result) == 1
    assert result[0].offer_id == "offer-from-cache"


@pytest.mark.asyncio
async def test_cache_miss_for_tops_item_falls_back_to_db(mocker):
    """
    When the cache returns None for a tops item (miss), the spatial DB query
    is called and the result is used to build the enriched offer.
    """
    patch_all_caches_enabled(mocker)
    mocker.patch("core.offer_resolution.get_h3_index_from_coordinates", return_value="fake-h3-cell")
    mocker.patch(
        "core.offer_resolution.redis_api.mget_resolved_offers",
        new_callable=AsyncMock,
        return_value=[None],  # cache miss
    )
    mocker.patch("core.offer_resolution.redis_api.mset_resolved_offers", new_callable=AsyncMock)
    mocker.patch.object(
        RedisAPI, "calculate_seconds_until_next_database_population_time", return_value=_MOCK_TTL_SECONDS
    )

    item = RecommendableItemFactory.build(item_origin=ItemOrigin.TOPS, is_geolocated=True, total_offers=5)
    db_row = _make_db_row(item_id=item.item_id, offer_id="offer-from-db")

    mocker.patch(
        "core.offer_resolution.find_closest_offers_with_h3_index",
        new_callable=AsyncMock,
        return_value=[db_row],
    )

    user = UserContext(user_id="u", latitude=_PARIS[0], longitude=_PARIS[1])
    item_lookup_map = {item.item_id: item}

    result = await _resolve_multi_venue_items(MagicMock(), [item.item_id], item_lookup_map, user)

    assert len(result) == 1
    assert result[0].offer_id == "offer-from-db"


@pytest.mark.asyncio
async def test_db_resolved_tops_item_is_written_to_cache_after_miss(mocker):
    """
    After a cache miss, a tops item resolved via the DB must be stored in Redis
    (mset called once) so subsequent requests in the same H3 zone get a cache hit.
    """
    patch_all_caches_enabled(mocker)
    mocker.patch("core.offer_resolution.get_h3_index_from_coordinates", return_value="fake-h3-cell")
    mocker.patch(
        "core.offer_resolution.redis_api.mget_resolved_offers",
        new_callable=AsyncMock,
        return_value=[None],
    )
    mock_mset = mocker.patch("core.offer_resolution.redis_api.mset_resolved_offers", new_callable=AsyncMock)
    mocker.patch.object(
        RedisAPI, "calculate_seconds_until_next_database_population_time", return_value=_MOCK_TTL_SECONDS
    )

    item = RecommendableItemFactory.build(item_origin=ItemOrigin.TOPS, is_geolocated=True, total_offers=5)
    db_row = _make_db_row(item_id=item.item_id, offer_id="offer-from-db")

    mocker.patch(
        "core.offer_resolution.find_closest_offers_with_h3_index",
        new_callable=AsyncMock,
        return_value=[db_row],
    )

    user = UserContext(user_id="u", latitude=_PARIS[0], longitude=_PARIS[1])
    item_lookup_map = {item.item_id: item}

    await _resolve_multi_venue_items(MagicMock(), [item.item_id], item_lookup_map, user)

    mock_mset.assert_called_once()
    stored_entries, stored_ttl = mock_mset.call_args.args
    assert stored_ttl == _MOCK_TTL_SECONDS
    # The stored payload must include the offer_id resolved by the DB
    assert any(v["offer_id"] == "offer-from-db" for v in stored_entries.values())


@pytest.mark.asyncio
async def test_non_tops_item_bypasses_cache_read_and_write(mocker):
    """
    Non-tops items (USER_BASED, GRAPH) always go straight to the DB — they are
    never read from or written to the cache, even when OFFER_RESOLUTION_CACHE_ENABLED=True.
    """
    patch_all_caches_enabled(mocker)
    mocker.patch("core.offer_resolution.get_h3_index_from_coordinates", return_value="fake-h3-cell")
    mock_mget = mocker.patch("core.offer_resolution.redis_api.mget_resolved_offers", new_callable=AsyncMock)
    mock_mset = mocker.patch("core.offer_resolution.redis_api.mset_resolved_offers", new_callable=AsyncMock)

    item = RecommendableItemFactory.build(item_origin=ItemOrigin.USER_BASED, is_geolocated=True, total_offers=5)
    db_row = _make_db_row(item_id=item.item_id, offer_id="offer-from-db")

    mocker.patch(
        "core.offer_resolution.find_closest_offers_with_h3_index",
        new_callable=AsyncMock,
        return_value=[db_row],
    )

    user = UserContext(user_id="u", latitude=_PARIS[0], longitude=_PARIS[1])
    item_lookup_map = {item.item_id: item}

    result = await _resolve_multi_venue_items(MagicMock(), [item.item_id], item_lookup_map, user)

    # Non-tops items are never looked up in or written to cache
    mock_mget.assert_not_called()
    mock_mset.assert_not_called()
    assert len(result) == 1
    assert result[0].offer_id == "offer-from-db"


@pytest.mark.asyncio
async def test_cache_hit_venue_beyond_search_radius_is_dropped(mocker):
    """
    A cache hit whose venue coordinates are beyond MAX_DISTANCE_METERS_FOR_OFFER_RETRIEVAL
    (50 km) must be dropped, protecting against H3 zone boundary edge cases where a
    cached venue is no longer within the current user's search radius.
    """
    patch_all_caches_enabled(mocker)
    mocker.patch("core.offer_resolution.get_h3_index_from_coordinates", return_value="fake-h3-cell")
    # London is ~343 km from Paris — well beyond the 50 km search radius
    mocker.patch(
        "core.offer_resolution.redis_api.mget_resolved_offers",
        new_callable=AsyncMock,
        return_value=[_make_cached_payload(lat=_LONDON[0], lng=_LONDON[1])],
    )
    mocker.patch("core.offer_resolution.find_closest_offers_with_h3_index", new_callable=AsyncMock, return_value=[])

    user = UserContext(user_id="u", latitude=_PARIS[0], longitude=_PARIS[1])
    item = RecommendableItemFactory.build(item_origin=ItemOrigin.TOPS, is_geolocated=True, total_offers=5)
    item_lookup_map = {item.item_id: item}

    result = await _resolve_multi_venue_items(MagicMock(), [item.item_id], item_lookup_map, user)

    assert result == [], (
        f"Expected 0 results (venue too far), got {len(result)}. "
        f"MAX allowed: {MAX_DISTANCE_METERS_FOR_OFFER_RETRIEVAL} m"
    )


@pytest.mark.asyncio
async def test_partial_cache_hit_sends_only_misses_to_db(mocker):
    """
    With two tops items where one hits the cache and one misses, only the cache-miss
    item must be sent to the DB query. The total result contains both items.
    """
    patch_all_caches_enabled(mocker)
    mocker.patch("core.offer_resolution.get_h3_index_from_coordinates", return_value="fake-h3-cell")

    item_hit = RecommendableItemFactory.build(item_origin=ItemOrigin.TOPS, is_geolocated=True, total_offers=5)
    item_miss = RecommendableItemFactory.build(item_origin=ItemOrigin.TOPS, is_geolocated=True, total_offers=5)

    # First item hits cache, second misses
    mocker.patch(
        "core.offer_resolution.redis_api.mget_resolved_offers",
        new_callable=AsyncMock,
        return_value=[_make_cached_payload(offer_id="offer-cached"), None],
    )
    mocker.patch("core.offer_resolution.redis_api.mset_resolved_offers", new_callable=AsyncMock)
    mocker.patch.object(
        RedisAPI, "calculate_seconds_until_next_database_population_time", return_value=_MOCK_TTL_SECONDS
    )

    db_row = _make_db_row(item_id=item_miss.item_id, offer_id="offer-db-miss")
    mock_db_query = mocker.patch(
        "core.offer_resolution.find_closest_offers_with_h3_index",
        new_callable=AsyncMock,
        return_value=[db_row],
    )

    user = UserContext(user_id="u", latitude=_PARIS[0], longitude=_PARIS[1])
    item_lookup_map = {item_hit.item_id: item_hit, item_miss.item_id: item_miss}

    result = await _resolve_multi_venue_items(MagicMock(), [item_hit.item_id, item_miss.item_id], item_lookup_map, user)

    # DB was called only for the cache miss
    db_query_item_ids = mock_db_query.call_args.args[1]
    assert item_miss.item_id in db_query_item_ids
    assert item_hit.item_id not in db_query_item_ids

    offer_ids = {r.offer_id for r in result}
    assert offer_ids == {"offer-cached", "offer-db-miss"}


@pytest.mark.asyncio
async def test_unresolved_tops_item_not_stored_in_cache(mocker):
    """
    If the DB query returns no row for a tops cache-miss item (e.g. no venue within
    the search radius), mset must NOT be called — absence of resolution must never
    be cached to avoid serving a permanent empty result.
    """
    patch_all_caches_enabled(mocker)
    mocker.patch("core.offer_resolution.get_h3_index_from_coordinates", return_value="fake-h3-cell")
    mocker.patch(
        "core.offer_resolution.redis_api.mget_resolved_offers",
        new_callable=AsyncMock,
        return_value=[None],
    )
    mock_mset = mocker.patch("core.offer_resolution.redis_api.mset_resolved_offers", new_callable=AsyncMock)
    mocker.patch.object(
        RedisAPI, "calculate_seconds_until_next_database_population_time", return_value=_MOCK_TTL_SECONDS
    )

    # DB returns no rows → item not resolved
    mocker.patch(
        "core.offer_resolution.find_closest_offers_with_h3_index",
        new_callable=AsyncMock,
        return_value=[],
    )

    item = RecommendableItemFactory.build(item_origin=ItemOrigin.TOPS, is_geolocated=True, total_offers=5)
    user = UserContext(user_id="u", latitude=_PARIS[0], longitude=_PARIS[1])
    item_lookup_map = {item.item_id: item}

    result = await _resolve_multi_venue_items(MagicMock(), [item.item_id], item_lookup_map, user)

    assert result == []
    mock_mset.assert_not_called()

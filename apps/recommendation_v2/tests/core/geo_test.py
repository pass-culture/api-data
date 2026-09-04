from unittest.mock import AsyncMock
from unittest.mock import MagicMock

import pytest

from core.geo import calculate_haversine_distance_in_meters
from core.geo import get_iris_id_from_coordinates


# ---------------------------------------------------------------------------
# calculate_haversine_distance_in_meters
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("user_lat", "user_lon", "offer_lat", "offer_lon"),
    [
        (None, 2.35, 51.5, -0.13),
        (48.86, None, 51.5, -0.13),
        (48.86, 2.35, None, -0.13),
        (48.86, 2.35, 51.5, None),
    ],
)
def test_haversine_returns_none_when_any_coordinate_is_missing(user_lat, user_lon, offer_lat, offer_lon):
    assert calculate_haversine_distance_in_meters(user_lat, user_lon, offer_lat, offer_lon) is None


def test_haversine_computes_correct_distance_for_known_coordinates():
    # Paris → London ≈ 343,56 km ± 10m  source https://www.vcalc.com/wiki/vcalc/haversine-distance
    distance = calculate_haversine_distance_in_meters(48.8566, 2.3522, 51.5074, -0.1278)
    distance_precision_meters = 10
    assert distance is not None
    assert abs(distance - 343_560) <= distance_precision_meters


# ---------------------------------------------------------------------------
# get_iris_id_from_coordinates
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_iris_id_returns_none_when_coordinates_missing():
    db = AsyncMock()
    assert await get_iris_id_from_coordinates(db, None, 2.35) is None
    assert await get_iris_id_from_coordinates(db, 48.86, None) is None
    assert await get_iris_id_from_coordinates(db, None, None) is None
    db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_get_iris_id_returns_result_from_st_contains():
    """Happy path: ST_Contains matches — no centroid fallback needed."""
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = "iris-42"

    db = AsyncMock()
    db.execute.return_value = mock_result

    result = await get_iris_id_from_coordinates(db, 48.86, 2.35)

    assert result == "iris-42"
    assert db.execute.call_count == 1


@pytest.mark.asyncio
async def test_get_iris_id_falls_back_to_centroid_when_st_contains_misses():
    """
    Verifies the centroid KNN fallback fires when ST_Contains returns nothing
    (e.g. a point on a polygon boundary or just outside IRIS coverage).
    """
    miss_result = MagicMock()
    miss_result.scalars.return_value.first.return_value = None

    hit_result = MagicMock()
    hit_result.scalars.return_value.first.return_value = "iris-nearest"

    db = AsyncMock()
    db.execute.side_effect = [miss_result, hit_result]

    result = await get_iris_id_from_coordinates(db, 48.86, 2.35)

    assert result == "iris-nearest"
    assert db.execute.call_count == 2  # ST_Contains query + centroid fallback query


@pytest.mark.asyncio
async def test_get_iris_id_returns_none_when_both_queries_miss():
    """Point is genuinely outside all IRIS zones (e.g. overseas, invalid coords)."""
    miss_result = MagicMock()
    miss_result.scalars.return_value.first.return_value = None

    db = AsyncMock()
    db.execute.side_effect = [miss_result, miss_result]

    result = await get_iris_id_from_coordinates(db, 0.0, 0.0)

    assert result is None
    assert db.execute.call_count == 2

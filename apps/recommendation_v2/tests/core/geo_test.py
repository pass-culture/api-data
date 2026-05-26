import pytest

from core.geo import calculate_haversine_distance_in_meters


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

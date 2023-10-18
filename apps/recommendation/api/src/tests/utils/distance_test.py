from huggy.utils.distance import haversine_distance

# Coordinates for Paris and Marseille
paris_lat = 48.8566
paris_lon = 2.3522
marseille_lat = 43.2965
marseille_lon = 5.3698
expected_distance = 660478


def test_haversine_distance():
    distance = haversine_distance(paris_lat, paris_lon, marseille_lat, marseille_lon)
    assert (distance - expected_distance) // 1000 == 0, "distance should be equal"

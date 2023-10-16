import math


def haversine_distance(lat1, lon1, lat2, lon2):
    if lat1 is None:
        return None
    if lon1 is None:
        return None
    if lat2 is None:
        return None
    if lon2 is None:
        return None

    earth_radius = 6371
    lat1 = math.radians(lat1)
    lon1 = math.radians(lon1)
    lat2 = math.radians(lat2)
    lon2 = math.radians(lon2)

    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    distance = earth_radius * c

    return distance * 1000

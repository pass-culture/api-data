import math


def haversine_distance(venue_latitude, venue_longitude, user_latitude, user_longitude):
    if venue_latitude is None:
        return None
    if venue_longitude is None:
        return None
    if user_latitude is None:
        return None
    if user_longitude is None:
        return None

    earth_radius = 6371
    venue_latitude = math.radians(venue_latitude)
    venue_longitude = math.radians(venue_longitude)
    user_latitude = math.radians(user_latitude)
    user_longitude = math.radians(user_longitude)

    dlat = user_latitude - venue_latitude
    dlon = user_longitude - venue_longitude
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(venue_latitude) * math.cos(user_latitude) * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    distance = earth_radius * c

    return distance * 1000

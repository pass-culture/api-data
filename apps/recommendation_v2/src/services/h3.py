import math

import h3


def get_h3_index_from_coordinates(latitude: float | None, longitude: float | None, *, resolution) -> str | None:
    """
    Returns the H3 index for the given coordinates and resolution.
    Returns None if latitude or longitude is missing.
    """
    if latitude is None or longitude is None:
        return None
    return h3.latlng_to_cell(latitude, longitude, resolution)


def calculate_h3_k_rings_to_cover_search_radius(search_radius_in_km: float, *, resolution) -> int:
    """
    Calculates the number of H3 k-rings required to completely cover a given search radius.

    In H3, grid distances are measured in "rings" around a central cell. To ensure that
    we retrieve all cells within a circular radius, we estimate the number of rings based
    on the average size of a hexagon at the given resolution.

    The constant 1.732 is an approximation of sqrt(3). In a regular hexagon, the distance
    between the centers of two adjacent hexagons is `edge_length * sqrt(3)`.

    Args:
        search_radius_in_km (float): The maximum distance in kilometers to cover.
        resolution (int): The H3 resolution used for the grid.

    Returns:
        int: The number of k-rings needed to cover the search radius.
    """
    # 1. Retrieve the average edge length for the specified resolution
    average_hexagon_edge_length_in_km = h3.average_hexagon_edge_length(resolution, unit="km")

    # 2. Approximate the distance between two adjacent hexagon centers
    distance_between_centers_in_km = average_hexagon_edge_length_in_km * 1.732

    # 3. Calculate the required number of rings and add 1 for a safety margin
    required_number_of_rings = math.ceil(search_radius_in_km / distance_between_centers_in_km) + 1

    return required_number_of_rings

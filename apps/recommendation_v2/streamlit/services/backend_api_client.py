"""
Client module logic for communicating with external APIs.
"""

from http import HTTPStatus

import requests


# Configuration URLs and Headers
BACKEND_BASE_URL = "https://backend.staging.passculture.team"
HEADERS = {}


def fetch_playlist_recommendation_ids(api_url: str, params: dict, payload: dict) -> tuple[list[str], str, str]:
    """
    Executes a POST request to retrieve recommendation data.

    Parameters:
    - api_url (str): The full endpoint URL.
    - params (dict): URL query parameters.
    - payload (dict): JSON body content.

    Returns:
    - Tuple: (list of offer IDs, reco origin string, model origin string).
    """
    response = requests.post(api_url, params=params, json=payload)
    response.raise_for_status()

    data = response.json()

    # Extract structural metadata
    params_out = data.get("params", {})
    reco_origin = params_out.get("reco_origin", "N/A")
    model_origin = params_out.get("model_origin", "N/A")

    # Safely extract formatting logic for offer_ids
    offer_ids_raw = data.get("playlist_recommended_offers", [])
    if not isinstance(offer_ids_raw, list):
        offer_ids_raw = data if isinstance(data, list) else []

    return offer_ids_raw, reco_origin, model_origin


def fetch_similar_offer_ids(api_url: str, params: dict) -> tuple[list[str], str, str]:
    """
    Executes a GET request to retrieve similar offers data.

    Parameters:
    - api_url (str): The full endpoint URL.
    - params (dict): URL query parameters.

    Returns:
    - Tuple: (list of offer IDs, reco origin string, model origin string).
    """
    response = requests.get(api_url, params=params)
    response.raise_for_status()

    data = response.json()

    # Extract structural metadata
    params_out = data.get("params", {})
    reco_origin = params_out.get("reco_origin", "N/A")
    model_origin = params_out.get("model_origin", "N/A")

    # Safely extract formatting logic for offer_ids
    offer_ids_raw = data.get("results", [])
    if not isinstance(offer_ids_raw, list):
        offer_ids_raw = data if isinstance(data, list) else []

    return offer_ids_raw, reco_origin, model_origin


def fetch_offer_details(offer_id: str) -> dict | None:
    """
    Fetches detailed JSON metadata for a specific offer ID from the backend.

    Parameters:
    - offer_id (str): The unique identifier of the offer.

    Returns:
    - dict | None: Offer payload, or None if the request fails.
    """
    detail_url = f"{BACKEND_BASE_URL}/native/v3/offer/{offer_id}"
    try:
        detail_resp = requests.get(detail_url, headers=HEADERS)
        if detail_resp.status_code == HTTPStatus.OK:
            return detail_resp.json()
    except Exception:
        pass

    return None


def fetch_similar_artist_ids(api_url: str, params: dict) -> tuple[list[dict], str]:
    """
    Executes a GET request to retrieve similar artists data.

    Returns:
    - Tuple: (list of {artist_id_match, rank} dicts, call_id string)
    """
    response = requests.get(api_url, params=params)
    response.raise_for_status()

    data = response.json()
    call_id = data.get("params", {}).get("call_id", "N/A")

    similar_artists_raw = data.get("similar_artists", [])
    if not isinstance(similar_artists_raw, list):
        similar_artists_raw = []

    return similar_artists_raw, call_id

"""
HTTP client for communicating with the recommendation API and the backend offer detail API.
"""

from http import HTTPStatus

import requests


BACKEND_BASE_URL = "https://backend.staging.passculture.team"
BACKEND_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
}


def _inject_token(params: dict, api_token: str | None) -> dict:
    """Return a copy of params with the API token appended if provided."""
    if api_token:
        return {**params, "token": api_token}
    return params


def fetch_playlist_recommendation_ids(
    api_url: str,
    params: dict,
    payload: dict,
    proxies: dict | None = None,
    api_token: str | None = None,
) -> tuple[list[str], str, str]:
    """POST to the playlist recommendation endpoint and return offer IDs with metadata.

    Args:
        api_url: Full endpoint URL.
        params: URL query parameters (e.g. geolocation).
        payload: JSON request body (filters and options).
        proxies: Optional SOCKS5 proxy dict for VPC tunneling.
        api_token: Optional API token injected as query param `?token=`.

    Returns:
        Tuple of (offer_ids, reco_origin, model_origin).
    """
    response = requests.post(api_url, params=_inject_token(params, api_token), json=payload, proxies=proxies)
    response.raise_for_status()

    data = response.json()
    response_params = data.get("params", {})

    offer_ids = data.get("playlist_recommended_offers", [])
    if not isinstance(offer_ids, list):
        offer_ids = data if isinstance(data, list) else []

    return offer_ids, response_params.get("reco_origin", "N/A"), response_params.get("model_origin", "N/A")


def fetch_similar_offer_ids(
    api_url: str,
    params: dict,
    proxies: dict | None = None,
    api_token: str | None = None,
) -> tuple[list[str], str, str]:
    """GET the similar offers endpoint and return offer IDs with metadata.

    Args:
        api_url: Full endpoint URL.
        params: URL query parameters.
        proxies: Optional SOCKS5 proxy dict for VPC tunneling.
        api_token: Optional API token injected as query param `?token=`.

    Returns:
        Tuple of (offer_ids, reco_origin, model_origin).
    """
    response = requests.get(api_url, params=_inject_token(params, api_token), proxies=proxies)
    response.raise_for_status()

    data = response.json()
    response_params = data.get("params", {})

    offer_ids = data.get("results", [])
    if not isinstance(offer_ids, list):
        offer_ids = data if isinstance(data, list) else []

    return offer_ids, response_params.get("reco_origin", "N/A"), response_params.get("model_origin", "N/A")


def fetch_similar_artist_ids(
    api_url: str,
    params: dict,
    proxies: dict | None = None,
    api_token: str | None = None,
) -> tuple[list[dict], str]:
    """GET the similar artists endpoint and return artist matches with a call ID.

    Args:
        api_url: Full endpoint URL.
        params: URL query parameters.
        proxies: Optional SOCKS5 proxy dict for VPC tunneling.
        api_token: Optional API token injected as query param `?token=`.

    Returns:
        Tuple of (similar_artists list of {artist_id_match, rank}, call_id).
    """
    response = requests.get(api_url, params=_inject_token(params, api_token), proxies=proxies)
    response.raise_for_status()

    data = response.json()

    similar_artists = data.get("similar_artists", [])
    if not isinstance(similar_artists, list):
        similar_artists = []

    return similar_artists, data.get("params", {}).get("call_id", "N/A")


def fetch_offer_details(offer_id: str) -> dict | None:
    """Fetch display metadata for a single offer from the backend API.

    Args:
        offer_id: The unique offer identifier.

    Returns:
        Offer payload dict, or None if the request fails.
    """
    detail_url = f"{BACKEND_BASE_URL}/native/v3/offer/{offer_id}"
    try:
        response = requests.get(detail_url, headers=BACKEND_HEADERS)
        if response.status_code == HTTPStatus.OK:
            return response.json()
    except Exception:
        pass

    return None

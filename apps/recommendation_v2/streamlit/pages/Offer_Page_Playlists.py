"""
Offer Page Playlists Page for the Streamlit Recommendation Application.

Visualizes the aggregated response of the `/offer_page_playlists/{offer_id}` endpoint,
which returns several titled "similar offer" playlists in a single round-trip.
"""

import sys
import time as time_mod
from pathlib import Path

import requests

import streamlit as st


# Ensure internal imports from 'src' work smoothly
sys.path.append(str(Path(__file__).resolve().parent.parent.parent / "src"))

from components.card_renderer import show_recommendations
from components.card_renderer import show_similar_offer_source
from components.env_banner import render_env_banner
from components.request_debug import render_request_debug
from components.sidebar import render_offer_page_playlists_sidebar
from services.backend_api_client import fetch_offer_page_playlists


def main():
    """
    Coordinates the execution flow of the offer_page_playlists app.
    """
    st.set_page_config(page_title="Playlists Page Offre", layout="wide")

    st.title("✨ Proxy de l'API de Recommandation V2 - Playlists Page Offre")
    st.markdown(
        "Exécutez et testez l'endpoint `offer_page_playlists`, qui renvoie plusieurs "
        "playlists de recommandation en un seul appel."
    )

    # Collect parameters from the sidebar
    (
        offer_id,
        search_group_name,
        user_id,
        params,
        max_offers_to_fetch,
        run_fetch,
        api_base_url,
        proxies,
        api_token,
    ) = render_offer_page_playlists_sidebar()

    render_env_banner(api_base_url)

    if offer_id:
        with st.spinner("Récupération de l'offre source..."):
            show_similar_offer_source(offer_id=offer_id, title="Offre source")

    if run_fetch and offer_id:
        st.markdown("---")
        fetch_and_display_offer_page_playlists(
            offer_id, search_group_name, user_id, params, max_offers_to_fetch, api_base_url, proxies, api_token
        )
    elif run_fetch and not offer_id:
        st.error("Veuillez renseigner un ID d'offre dans la barre latérale.")


def fetch_and_display_offer_page_playlists(  # noqa: PLR0913
    offer_id: str,
    search_group_name: str,
    user_id: str | None,
    params: dict,
    max_offers: int,
    api_base_url: str,
    proxies: dict | None = None,
    api_token: str | None = None,
):
    """
    Calls the FastAPI backend to retrieve all offer page playlists and renders them.
    """
    api_url = f"{api_base_url.rstrip('/')}/offer_page_playlists/{offer_id}"

    # Build query params
    query_params = {**params}
    query_params["search_group_name"] = search_group_name
    if user_id:
        query_params["user_id"] = user_id

    with st.spinner("Appel de l'API offer_page_playlists en cours..."):
        start_time = time_mod.time()

        try:
            playlists, from_cache = fetch_offer_page_playlists(api_url, query_params, proxies, api_token)
        except requests.exceptions.RequestException as error:
            st.error(f"Erreur lors de l'appel de l'API : {error}")
            if error.response is not None:
                st.json(error.response.json())
            st.stop()

        api_response_time = time_mod.time() - start_time

    render_request_debug(method="GET", url=api_url, query_params=query_params, proxies=proxies)

    # Display execution metadata
    cache_badge = (
        '<span style="background:#4caf50; color:white; font-weight:700; padding:2px 8px; '
        'border-radius:10px; font-size:12px;">CACHE HIT</span>'
        if from_cache
        else '<span style="background:#9e9e9e; color:white; font-weight:700; padding:2px 8px; '
        'border-radius:10px; font-size:12px;">CACHE MISS</span>'
    )
    st.markdown(
        f"""
        <div style="display: flex; gap: 24px; align-items: center; background-color: #f8f9fa;
        padding: 12px 16px; border-radius: 8px; border: 1px solid #e9ecef; margin-bottom: 16px; color: #1f2937;">
            <div style="font-size: 14px;"><b>⏱ Temps d'exécution :</b> {api_response_time:.2f}s</div>
            <div style="font-size: 14px;"><b>📦 Playlists :</b> {len(playlists)}</div>
            <div style="font-size: 14px;">{cache_badge}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not playlists:
        st.warning("Aucune playlist n'a été retournée par le moteur.")
        return

    st.success("Récupération des détails effectuée.")

    # Render each titled playlist in the order returned by the backend
    for playlist in playlists:
        title = playlist.get("title", "Playlist")
        playlist_type = playlist.get("playlist_type", "N/A")
        offer_ids = playlist.get("results", [])
        playlist_params = playlist.get("params", {}) or {}
        reco_origin = playlist_params.get("reco_origin", "N/A")
        model_origin = playlist_params.get("model_origin", "N/A")

        st.markdown("---")
        st.markdown(
            f"""
            <div style="display: flex; gap: 24px; align-items: center; background-color: #eef2ff;
            padding: 10px 16px; border-radius: 8px; border: 1px solid #c7d2fe; margin-bottom: 8px; color: #1f2937;">
                <div style="font-size: 15px;"><b>🏷️ Type :</b> {playlist_type}</div>
                <div style="font-size: 14px;"><b>⚙️ Origine :</b> {str(reco_origin).capitalize()}</div>
                <div style="font-size: 14px;"><b>🧠 Modèle :</b> {str(model_origin).capitalize()}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if not offer_ids:
            st.warning(f"Aucune offre retournée pour la playlist « {title} ».")
            continue

        show_recommendations(
            offer_ids=offer_ids,
            max_offers_to_fetch=max_offers,
            latitude=params.get("latitude"),
            longitude=params.get("longitude"),
            title=title,
        )


if __name__ == "__main__":
    main()

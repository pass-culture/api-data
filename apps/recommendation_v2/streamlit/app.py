"""
Main entry point for the Streamlit Recommendation Application.

This module sets up the page configuration, displays the main UI,
coordinates the user inputs from the sidebar, fetches recommendations,
and delegates the rendering of the offer cards.
"""

import sys
import time as time_mod
from pathlib import Path

import requests

import streamlit as st


# Ensure internal imports from 'src' work smoothly
sys.path.append(str(Path(__file__).resolve().parent.parent / "src"))

from components.card_renderer import show_recommendations
from components.sidebar import render_sidebar
from services.backend_api_client import fetch_recommendation_ids

from config.settings import FASTAPI_SERVER_PORT


def main():
    """
    Coordinates the execution flow of the recommendation app.

    1. Sets up the Streamlit page.
    2. Renders the interactive sidebar to collect parameters.
    3. Handles the API call when the user clicks 'Fetch'.
    4. Renders the received recommendation offers.
    """
    st.set_page_config(page_title="API de Recommandation V2", layout="wide")

    st.title("✨ Proxy de l'API de Recommandation V2")
    st.markdown("Exécutez et testez l'API de recommandation en toute simplicité.")

    # Collect parameters from the sidebar
    user_id, params, payload, max_offers_to_fetch, run_fetch = render_sidebar()

    if run_fetch:
        fetch_and_display_recommendations(user_id, params, payload, max_offers_to_fetch)


def fetch_and_display_recommendations(user_id: str, params: dict, payload: dict, max_offers: int):
    """
    Calls the FastAPI backend to retrieve recommended offer IDs and renders them.

    Parameters:
    - user_id (str): The active user UUID.
    - params (dict): URL query parameters (like geolocation).
    - payload (dict): The request payload (filters and options).
    - max_offers (int): The maximum number of offers to display.
    """
    api_url = f"http://localhost:{FASTAPI_SERVER_PORT}/playlist_recommendation/{user_id}"

    with st.spinner("Appel de l'API de recommandation en cours..."):
        start_time = time_mod.time()

        try:
            offer_ids, reco_origin, model_origin = fetch_recommendation_ids(api_url, params, payload)
        except requests.exceptions.RequestException as error:
            st.error(f"Erreur lors de l'appel de l'API : {error}")
            if error.response is not None:
                st.json(error.response.json())
            st.stop()
            return

        api_response_time = time_mod.time() - start_time

    # Display execution metadata
    st.markdown(
        f"""
        <div style="display: flex; gap: 24px; align-items: center; background-color: #f8f9fa;
        padding: 12px 16px; border-radius: 8px; border: 1px solid #e9ecef; margin-bottom: 16px; color: #1f2937;">
            <div style="font-size: 14px;"><b>⏱ Temps d'exécution :</b> {api_response_time:.2f}s</div>
            <div style="font-size: 14px;"><b>⚙️ Origine :</b> {str(reco_origin).capitalize()}</div>
            <div style="font-size: 14px;"><b>🧠 Modèle :</b> {str(model_origin).capitalize()}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not offer_ids:
        st.warning("Aucune offre n'a été retournée par le moteur de recommandation.")
        return

    st.success("Récupération des détails des offres effectuée.")

    # Render the offers using our card renderer
    show_recommendations(
        offer_ids=offer_ids,
        max_offers_to_fetch=max_offers,
        latitude=params.get("latitude"),
        longitude=params.get("longitude"),
    )


if __name__ == "__main__":
    main()

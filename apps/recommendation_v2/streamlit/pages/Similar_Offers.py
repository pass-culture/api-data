"""
Similar Offers Page for the Streamlit Recommendation Application.
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
from components.sidebar import render_similar_offer_sidebar
from services.backend_api_client import fetch_similar_offer_ids


def main():
    """
    Coordinates the execution flow of the similar offers app.
    """
    st.set_page_config(page_title="Offres Similaires", layout="wide")

    st.title("✨ Proxy de l'API de Recommandation V2 - Offres Similaires")
    st.markdown("Exécutez et testez l'API d'offres similaires en toute simplicité.")

    # Collect parameters from the sidebar
    (
        offer_id,
        retrieval_model,
        user_id,
        params,
        payload,
        max_offers_to_fetch,
        run_fetch,
        api_base_url,
        proxies,
        api_token,
    ) = render_similar_offer_sidebar()

    render_env_banner(api_base_url)

    if offer_id:
        with st.spinner("Récupération de l'offre source..."):
            show_similar_offer_source(offer_id=offer_id, title="Offre source")

    if run_fetch and offer_id:
        st.markdown("---")
        fetch_and_display_similar_offers(
            offer_id, retrieval_model, user_id, params, payload, max_offers_to_fetch, api_base_url, proxies, api_token
        )
    elif run_fetch and not offer_id:
        st.error("Veuillez renseigner un ID d'offre dans la barre latérale.")


def fetch_and_display_similar_offers(  # noqa: PLR0913
    offer_id: str,
    retrieval_model: str,
    user_id: str | None,
    params: dict,
    payload: dict,
    max_offers: int,
    api_base_url: str,
    proxies: dict | None = None,
    api_token: str | None = None,
):
    """
    Calls the FastAPI backend to retrieve recommended similar offer IDs and renders them.
    """
    api_url = f"{api_base_url.rstrip('/')}/similar_offers/{offer_id}"

    # Build query params
    query_params = {**params}
    query_params["retrieval_model"] = retrieval_model
    if user_id:
        query_params["user_id"] = user_id

    # Merge payload filters that are supported by similar_offers into query params
    # According to similar_offer.py: categories, subcategories, search_group_names
    if "categories" in payload:
        query_params["categories"] = payload["categories"]
    if "subcategories" in payload:
        query_params["subcategories"] = payload["subcategories"]
    if "searchGroupNames" in payload:
        query_params["search_group_names"] = payload["searchGroupNames"]

    with st.spinner("Appel de l'API des offres similaires en cours..."):
        start_time = time_mod.time()

        try:
            offer_ids, reco_origin, model_origin = fetch_similar_offer_ids(api_url, query_params, proxies, api_token)
        except requests.exceptions.RequestException as error:
            st.error(f"Erreur lors de l'appel de l'API : {error}")
            if error.response is not None:
                st.json(error.response.json())
            st.stop()

        api_response_time = time_mod.time() - start_time

    render_request_debug(method="GET", url=api_url, query_params=query_params, proxies=proxies)

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
        st.warning("Aucune offre n'a été retournée par le moteur.")
        return

    st.success("Récupération des détails des offres effectuée.")

    # Render the offers using our card renderer
    show_recommendations(
        offer_ids=offer_ids,
        max_offers_to_fetch=max_offers,
        latitude=params.get("latitude"),
        longitude=params.get("longitude"),
        title="Offres similaires",
    )


if __name__ == "__main__":
    main()

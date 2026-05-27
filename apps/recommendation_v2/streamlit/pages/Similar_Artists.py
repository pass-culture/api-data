"""
Similar Artists Page for the Streamlit Recommendation Application.
"""

import time as time_mod
from http import HTTPStatus

import requests
from components.card_renderer import show_artist_source
from components.card_renderer import show_similar_artists
from services.backend_api_client import fetch_similar_artist_ids
from services.bigquery_client import fetch_artist_details
from services.bigquery_client import fetch_artists_details_batch

import streamlit as st
from config.settings import FASTAPI_SERVER_PORT


def main():
    st.set_page_config(page_title="Artistes Similaires", layout="wide")

    st.title("🎵 Proxy de l'API de Recommandation V2 - Artistes Similaires")

    with st.sidebar:
        st.header("Paramètres de la Requête")

        PRESET_ARTISTS = {
            "Damso": "a3a7c9f7-26f1-4bd3-bfc2-40a7abd398cf",
            "Aya Nakamura": "149c2bde-2385-49d1-86ec-88f0b9472fbe",
            "Chopin": "b4162c08-86bb-4063-b859-d9c5e7168938",
            "Adele": "59f6356c-eb22-4ef9-a666-19a97baad1b9",
            "Charles Aznavour": "52ea853b-c04b-425d-adac-a16b862db0cd",
            "Nina Simone": "9c9d6a0b-4d57-4a02-9443-3e71f86bb212",
            "Bad Bunny": "405baa4b-2652-4ad3-85ce-e1add80c4fc1",
            "Souad Massi": "d3f84f81-39a7-4781-b8a8-7a5a307cc24c",
            "Autre": None,
        }

        selected = st.selectbox("Artiste", options=list(PRESET_ARTISTS.keys()))

        if PRESET_ARTISTS[selected] is None:
            artist_id = st.text_input("ID de l'artiste", placeholder="ex: 0c1a0fe4-f2bf-4e1d-b9ac-7c46e4a6e2d6")
        else:
            artist_id = PRESET_ARTISTS[selected]

        run_fetch = st.button("🚀 Obtenir les artistes similaires", type="primary")

    if artist_id:
        with st.spinner("Récupération de l'artiste source..."):
            source_artist = fetch_artist_details(artist_id)
        if source_artist:
            show_artist_source(source_artist, title="Artiste source")
        else:
            st.warning(f"Artiste `{artist_id}` introuvable dans BigQuery.")

    if run_fetch and artist_id:
        st.markdown("---")
        _fetch_and_display_similar_artists(artist_id)
    elif run_fetch and not artist_id:
        st.error("Veuillez renseigner un ID d'artiste dans la barre latérale.")


def _fetch_and_display_similar_artists(artist_id: str):
    api_url = f"http://localhost:{FASTAPI_SERVER_PORT}/similar_artists/{artist_id}"

    with st.spinner("Appel de l'API des artistes similaires en cours..."):
        start_time = time_mod.time()

        try:
            similar_artists, call_id = fetch_similar_artist_ids(api_url, params={})
        except requests.exceptions.HTTPError as error:
            if error.response is not None and error.response.status_code == HTTPStatus.NOT_FOUND:
                st.warning(f"Artiste `{artist_id}` introuvable dans la table des artistes similaires.")
            else:
                st.error(f"Erreur lors de l'appel de l'API : {error}")
                if error.response is not None:
                    st.json(error.response.json())
            st.stop()
        except requests.exceptions.RequestException as error:
            st.error(f"Erreur lors de l'appel de l'API : {error}")
            st.stop()

        api_response_time = time_mod.time() - start_time

    st.markdown(
        f"""
        <div style="display: flex; gap: 24px; align-items: center; background-color: #f8f9fa;
        padding: 12px 16px; border-radius: 8px; border: 1px solid #e9ecef; margin-bottom: 16px; color: #1f2937;">
            <div style="font-size: 14px;"><b>⏱ Temps d'exécution :</b> {api_response_time:.2f}s</div>
            <div style="font-size: 14px;"><b>🔑 Call ID :</b> {call_id}</div>
            <div style="font-size: 14px;"><b>🎵 Artistes retournés :</b> {len(similar_artists)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not similar_artists:
        st.warning("Aucun artiste similaire retourné par le moteur.")
        return

    artist_ids = [item["artist_id_match"] for item in similar_artists]
    with st.spinner("Récupération des détails des artistes depuis BigQuery..."):
        artist_details_map = fetch_artists_details_batch(artist_ids)

    show_similar_artists(
        similar_artists=similar_artists,
        artist_details_map=artist_details_map,
        title="Artistes similaires",
    )


if __name__ == "__main__":
    main()

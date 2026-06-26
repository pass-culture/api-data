"""
Sidebar component for the Streamlit Application.

Presents form inputs to construct parameters and payload for the recommendation API.
"""

import os
from datetime import datetime
from datetime import time

import folium
from geopy.geocoders import Nominatim
from services.database_service import get_random_offer
from services.database_service import get_random_user
from streamlit_folium import st_folium

import streamlit as st
from config.settings import FASTAPI_SERVER_PORT
from config.settings import SWAGGER_UI_EXAMPLE_OFFER_ID
from config.settings import SWAGGER_UI_EXAMPLE_USER_ID
from schemas.playlist_recommendation import CategoryEnum
from schemas.playlist_recommendation import SearchGroupNameEnum
from schemas.playlist_recommendation import SubcategoryEnum
from schemas.similar_offer import SimilarOfferModelChoices
from utils.location_presets import PRESET_LOCATION_TO_GEOGRAPHIC_COORDINATES_MAPPING


_LOCAL_HOST_PATTERNS = ("localhost", "127.0.0.", "0.0.0.0")

V1_LABEL = "v1 (legacy)"
V2_LABEL = "v2 (default)"


def _render_api_url_input(default_url: str | None = None) -> tuple[str, dict | None, str | None]:
    """Render the API connection block in the sidebar.

    Displays:
    - API base URL input (always visible, pre-filled from REMOTE_API_URL env var if set)
    - API version radio selector (only if URL is remote AND REMOTE_API_V1_URL is set)
    - API token input (only if URL is remote)
    - SOCKS5 proxy input (only if URL is remote)

    The version selector pre-selects v1 or v2 based on the STREAMLIT_DEFAULT_API_VERSION
    environment variable set by the Makefile (e.g. VERSION=1 → pre-select v1).

    Returns:
        tuple: (api_url, proxies dict or None, api_token or None)
    """
    if default_url is None:
        default_url = f"http://localhost:{FASTAPI_SERVER_PORT}"

    remote_v1_url = os.environ.get("REMOTE_API_V1_URL", "")
    remote_v2_url = os.environ.get("REMOTE_API_URL", "") or default_url

    # Version selector is rendered first so it updates api_base_url
    # in session_state before the URL text_input reads it.
    if remote_v1_url:
        _render_api_version_selector(remote_v1_url, remote_v2_url)

    # --- API URL ---
    st.markdown("**URL de l'API**")
    api_url = st.text_input(
        "URL de base de l'API FastAPI",
        value=st.session_state.get("api_base_url", remote_v2_url),
        help="Ex: http://localhost:8080 ou https://mon-api.example.com",
        label_visibility="collapsed",
        placeholder="http://localhost:8080",
    )
    st.session_state.api_base_url = api_url

    is_local_url = any(pattern in api_url for pattern in _LOCAL_HOST_PATTERNS)

    if is_local_url:
        st.session_state.api_token = ""
        return api_url, None, None

    # --- Remote-only fields ---

    # Token
    st.markdown("**Token API**")
    api_token = st.text_input(
        "Token API",
        value=st.session_state.get("api_token", os.environ.get("REMOTE_API_TOKEN", "")),
        help="Requis pour les APIs distantes. Passé en query param `?token=`.",
        label_visibility="collapsed",
        placeholder="mon-token-secret",
        type="password",
    )
    st.session_state.api_token = api_token

    # SOCKS5 proxy
    st.markdown("**Proxy SOCKS5 (optionnel)**")
    socks_proxy = st.text_input(
        "Proxy SOCKS5",
        value=st.session_state.get("socks_proxy", "socks5h://localhost:1080"),
        help="Laissez vide si inutile. Ex: socks5h://localhost:1080 (tunnel SSH via gcloud).",
        label_visibility="collapsed",
        placeholder="socks5h://localhost:1080",
    )
    st.session_state.socks_proxy = socks_proxy

    proxies = None
    if socks_proxy.strip():
        proxies = {"http": socks_proxy.strip(), "https": socks_proxy.strip()}

    return st.session_state.api_base_url, proxies, api_token.strip() or None


def _render_api_version_selector(remote_v1_url: str, remote_v2_url: str) -> None:
    """Render the v1/v2 radio selector and update the API URL in session state.

    Args:
        remote_v1_url: The base URL of the v1 (legacy) API.
        remote_v2_url: The base URL of the v2 (default) API.
    """
    st.markdown("**Version de l'API**")
    selected_version = st.radio(
        "Version de l'API",
        [V2_LABEL, V1_LABEL],
        horizontal=True,
        label_visibility="collapsed",
        key="api_version_selector",
    )

    # Always sync the URL with the currently selected version
    st.session_state.api_base_url = remote_v1_url if selected_version == V1_LABEL else remote_v2_url


def render_playlist_recommendation_sidebar() -> tuple:
    """
    Displays the sidebar and gathers inputs from the user for the playlist recommendation.

    Returns:
    - tuple: (user_id, params dict, payload dict, max_offers_to_fetch,
              run_fetch_boolean, api_base_url, proxies, api_token)
    """
    with st.sidebar:
        st.header("1. Paramètres de la Requête")

        api_base_url, proxies, api_token = _render_api_url_input()

        st.divider()

        # User identification
        st.markdown("**Sélection de l'utilisateur**")
        user_id_input = st.text_input(
            "Identifiant utilisateur",
            value=st.session_state.get("user_id", SWAGGER_UI_EXAMPLE_USER_ID),
            help="UUID de l'utilisateur",
            label_visibility="collapsed",
        )
        st.session_state.user_id = user_id_input

        _render_random_user_buttons()

        st.divider()

        user_id = st.session_state.user_id

        # Geolocation selection
        latitude, longitude = _render_geolocation_inputs()

        # Payload Configuration Blocks
        st.subheader("Filtres et Options (Payload)")
        payload = _render_playlist_recommendation_payload_filters()

        # Display and action
        st.subheader("Options d'Affichage")
        max_offers_to_fetch = st.number_input(
            "Nombre d'offres maximum à récupérer", min_value=1, max_value=60, value=20
        )

        run_btn = st.button("🚀 Obtenir les Recommandations", type="primary")

        # Mapping properties
        params = {}
        if latitude is not None and longitude is not None:
            params["latitude"] = latitude
            params["longitude"] = longitude

        return user_id, params, payload, max_offers_to_fetch, run_btn, api_base_url, proxies, api_token


def render_similar_offer_sidebar() -> tuple:
    """
    Displays the sidebar and gathers inputs from the user for similar offers.

    Returns:
    - tuple: (offer_id, retrieval_model, user_id, params dict, payload dict, max_offers_to_fetch,
              run_fetch_boolean, api_base_url, proxies, api_token)
    """
    with st.sidebar:
        st.header("1. Paramètres de la Requête")

        api_base_url, proxies, api_token = _render_api_url_input()

        st.divider()

        # Offer identification
        st.markdown("**Sélection de l'offre**")
        offer_id_input = st.text_input(
            "Identifiant de l'offre source",
            value=st.session_state.get("similar_offer_id", SWAGGER_UI_EXAMPLE_OFFER_ID),
            help="ID de l'offre (MongoID) pour laquelle chercher des similaires",
            label_visibility="collapsed",
            placeholder="26429343",
        )
        st.session_state.similar_offer_id = offer_id_input

        _render_random_offer_button()

        st.divider()

        # Model selection
        st.subheader("Modèle de Similarité")
        retrieval_model = st.selectbox(
            "Sélectionnez le modèle de similarité à utiliser",
            [e.value for e in SimilarOfferModelChoices],
            index=1,
        )

        # Optional user identification
        st.markdown("**Utilisateur (optionnel)**")
        user_id_input = st.text_input(
            "Identifiant utilisateur",
            value=st.session_state.get("similar_offer_user_id", ""),
            help="UUID de l'utilisateur pour personnaliser les similaires (optionnel)",
            label_visibility="collapsed",
            placeholder="Laisser vide pour ignorer",
        )
        st.session_state.similar_offer_user_id = user_id_input

        _render_random_user_buttons(session_key="similar_offer_user_id")

        st.divider()

        offer_id = st.session_state.similar_offer_id
        user_id = st.session_state.similar_offer_user_id or None

        # Geolocation selection
        latitude, longitude = _render_geolocation_inputs()

        # Payload Configuration Blocks
        st.subheader("Filtres")
        payload = _render_similar_offer_filters()

        # Display and action
        st.subheader("Options d'Affichage")
        max_offers_to_fetch = st.number_input(
            "Nombre d'offres maximum à récupérer", min_value=1, max_value=20, value=20
        )

        run_btn = st.button("🚀 Rechercher des Similaires", type="primary")

        # Mapping properties
        params = {}
        if latitude is not None and longitude is not None:
            params["latitude"] = latitude
            params["longitude"] = longitude

        return (
            offer_id,
            retrieval_model,
            user_id,
            params,
            payload,
            max_offers_to_fetch,
            run_btn,
            api_base_url,
            proxies,
            api_token,
        )


def _render_random_user_buttons(session_key: str = "user_id"):
    """Renders buttons to fetch a random 'warm' or 'cold start' user."""
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🎲 Actif", use_container_width=True, key=f"btn_active_{session_key}"):
            with st.spinner("Recherche d'un utilisateur actif..."):
                uid = get_random_user(is_cold_start=False)
                if uid:
                    st.session_state[session_key] = uid
                    st.rerun()
                else:
                    st.toast("Aucun utilisateur actif trouvé", icon="❌")
    with col2:
        if st.button("🎲 Cold Start", use_container_width=True, key=f"btn_cold_{session_key}"):
            with st.spinner("Recherche d'un utilisateur cold start..."):
                uid = get_random_user(is_cold_start=True)
                if uid:
                    st.session_state[session_key] = uid
                    st.rerun()
                else:
                    st.toast("Aucun utilisateur cold start trouvé", icon="❌")


def _render_random_offer_button():
    """Renders a button to fetch a random offer from the database."""
    if st.button("🎲 Offre aléatoire", use_container_width=True):
        with st.spinner("Recherche d'une offre aléatoire..."):
            oid = get_random_offer()
            if oid:
                st.session_state.similar_offer_id = oid
                st.rerun()
            else:
                st.toast("Aucune offre trouvée", icon="❌")


def _render_geolocation_inputs() -> tuple:
    """
    Displays geolocation methodologies and computes latitude/longitude.

    Returns:
    - tuple: (latitude float, longitude float)
    """
    st.subheader("Géolocalisation")
    location_mode = st.radio(
        "Mode de localisation",
        [
            "Sans géolocalisation",
            "Ville prédéfinie",
            "Saisie Adresse / Code postal",
            "Point sur une carte",
            "Coordonnées manuelles",
        ],
        index=1,
    )

    latitude, longitude = None, None

    if location_mode == "Ville prédéfinie":
        preset_names = [loc.value for loc in PRESET_LOCATION_TO_GEOGRAPHIC_COORDINATES_MAPPING]
        selected_city_val = st.selectbox("Sélectionnez une ville", preset_names)

        # Find numeric coordinates based on enum matching
        selected_key = next(
            k for k in PRESET_LOCATION_TO_GEOGRAPHIC_COORDINATES_MAPPING if k.value == selected_city_val
        )
        latitude, longitude = PRESET_LOCATION_TO_GEOGRAPHIC_COORDINATES_MAPPING[selected_key]

    elif location_mode == "Saisie Adresse / Code postal":
        address_input = st.text_input(
            "Saisissez une adresse, un code postal ou une ville", placeholder="ex: 75001 Paris"
        )

        if address_input:
            geolocator = Nominatim(user_agent="pass_culture_reco_v2_proxy")
            with st.spinner("Recherche des coordonnées..."):
                try:
                    location = geolocator.geocode(address_input, country_codes="FR")
                    if location:
                        st.success(f"📍 {location.address}")
                        latitude = location.latitude
                        longitude = location.longitude
                    else:
                        st.error("Aucune position trouvée.")
                except Exception as e:
                    st.error(f"Erreur de géocodage: {e}")

    elif location_mode == "Point sur une carte":
        st.write("Cliquez n'importe où sur la carte pour récupérer les coordonnées.")
        map_instance = folium.Map(location=[46.6033, 1.8883], zoom_start=5)
        map_instance.add_child(folium.LatLngPopup())

        map_data = st_folium(map_instance, height=400, use_container_width=True)
        if map_data and map_data.get("last_clicked"):
            lat = map_data["last_clicked"]["lat"]
            lng = map_data["last_clicked"]["lng"]
            st.success(f"📍 Mémorisé : Lat {lat:.4f} / Lon {lng:.4f}")
            latitude, longitude = lat, lng

    elif location_mode == "Coordonnées manuelles":
        latitude = st.number_input("Latitude", value=48.8566, format="%.4f")
        longitude = st.number_input("Longitude", value=2.3522, format="%.4f")

    return latitude, longitude


def _render_playlist_recommendation_payload_filters() -> dict:
    """Renders the expanders for filtering options and builds the json payload."""
    with st.expander("Contraintes Temporelles"):
        start_date_val = st.date_input("Date de début", value=None)
        end_date_val = st.date_input("Date de fin", value=None)
        is_event = st.selectbox("Événement", [None, True, False])

    with st.expander("Contraintes Contextuelles & Format"):
        is_duo = st.selectbox("Duo", [None, True, False])
        is_restrained = st.selectbox("Restreint", [True, False, None], index=0)
        is_digital = st.selectbox("Numérique", [None, True, False])

    with st.expander("Contraintes Financières"):
        price_min = st.number_input("Prix Minimum", value=None, min_value=0.0)
        price_max = st.number_input("Prix Maximum", value=None, max_value=150.0)

    with st.expander("Filtres Catégoriels"):
        categories = st.multiselect("Catégories", [e.value for e in CategoryEnum])
        subcategories = st.multiselect("Sous-catégories", [e.value for e in SubcategoryEnum])
        search_group_names = st.multiselect("Groupes de recherche", [e.value for e in SearchGroupNameEnum])

    # Assemble Payload Configuration Dictionary
    payload = {}
    if start_date_val:
        payload["startDate"] = datetime.combine(start_date_val, time.min).isoformat()
    if end_date_val:
        payload["endDate"] = datetime.combine(end_date_val, time.max).isoformat()
    if is_event is not None:
        payload["isEvent"] = is_event
    if is_duo is not None:
        payload["isDuo"] = is_duo
    if is_restrained is not None:
        payload["isRestrained"] = is_restrained
    if is_digital is not None:
        payload["isDigital"] = is_digital
    if price_min is not None:
        payload["priceMin"] = price_min
    if price_max is not None:
        payload["priceMax"] = price_max
    if categories:
        payload["categories"] = categories
    if subcategories:
        payload["subcategories"] = subcategories
    if search_group_names:
        payload["searchGroupNames"] = search_group_names

    return payload


def _render_similar_offer_filters() -> dict:
    """Renders the expanders for filtering options and builds the json payload for similar offers."""
    with st.expander("Filtres Catégoriels"):
        categories = st.multiselect("Catégories", [e.value for e in CategoryEnum])
        subcategories = st.multiselect("Sous-catégories", [e.value for e in SubcategoryEnum])
        search_group_names = st.multiselect("Groupes de recherche", [e.value for e in SearchGroupNameEnum])

    payload = {}
    if categories:
        payload["categories"] = categories
    if subcategories:
        payload["subcategories"] = subcategories
    if search_group_names:
        payload["searchGroupNames"] = search_group_names

    return payload

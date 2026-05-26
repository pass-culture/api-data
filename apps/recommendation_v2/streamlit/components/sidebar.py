"""
Sidebar component for the Streamlit Application.

Presents form inputs to construct parameters and payload for the recommendation API.
"""

from datetime import datetime
from datetime import time

import folium
from geopy.geocoders import Nominatim
from services.database_service import get_random_offer
from services.database_service import get_random_user
from streamlit_folium import st_folium

import streamlit as st
from config.settings import SWAGGER_UI_EXAMPLE_OFFER_ID
from config.settings import SWAGGER_UI_EXAMPLE_USER_ID
from schemas.playlist_recommendation import CategoryEnum
from schemas.playlist_recommendation import SearchGroupNameEnum
from schemas.playlist_recommendation import SubcategoryEnum
from schemas.similar_offer import SimilarOfferModelChoices
from utils.location_presets import PRESET_LOCATION_TO_GEOGRAPHIC_COORDINATES_MAPPING


def render_playlist_recommendation_sidebar() -> tuple:
    """
    Displays the sidebar and gathers inputs from the user for the playlist recommendation.

    Returns:
    - tuple: (user_id, params dict, payload dict, max_offers_to_fetch, run_fetch_boolean)
    """
    with st.sidebar:
        st.header("1. Paramètres de la Requête")

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

        return user_id, params, payload, max_offers_to_fetch, run_btn


def render_similar_offer_sidebar() -> tuple:
    """
    Displays the sidebar and gathers inputs from the user for similar offers.

    Returns:
    - tuple: (offer_id, retrieval_model, user_id, params dict, payload dict, max_offers_to_fetch, run_fetch_boolean)
    """
    with st.sidebar:
        st.header("1. Paramètres de la Requête")

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

        return offer_id, retrieval_model, user_id, params, payload, max_offers_to_fetch, run_btn


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


def _render_playlist_recommendation_payload_filters() -> dict:  # noqa: PLR0912, PLR0915
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

    with st.expander("Filtres GTL"):
        gtl_ids = st.text_input("Identifiants GTL (séparés par virgule)")
        gtl_l1 = st.text_input("GTL Niveau 1 (séparés par virgule)")
        gtl_l2 = st.text_input("GTL Niveau 2 (séparés par virgule)")
        gtl_l3 = st.text_input("GTL Niveau 3 (séparés par virgule)")
        gtl_l4 = st.text_input("GTL Niveau 4 (séparés par virgule)")

    with st.expander("Diversification & Pagination"):
        is_reco_shuffled = st.selectbox("Recommandations aléatoires (Shuffled)", [None, True, False])

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

    if gtl_ids:
        payload["gtlIds"] = [x.strip() for x in gtl_ids.split(",") if x.strip()]
    if gtl_l1:
        payload["gtlL1"] = [x.strip() for x in gtl_l1.split(",") if x.strip()]
    if gtl_l2:
        payload["gtlL2"] = [x.strip() for x in gtl_l2.split(",") if x.strip()]
    if gtl_l3:
        payload["gtlL3"] = [x.strip() for x in gtl_l3.split(",") if x.strip()]
    if gtl_l4:
        payload["gtlL4"] = [x.strip() for x in gtl_l4.split(",") if x.strip()]

    if is_reco_shuffled is not None:
        payload["isRecoShuffled"] = is_reco_shuffled

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

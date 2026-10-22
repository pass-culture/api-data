"""
Playlist Top Artists Page for the Streamlit Recommendation Application.

Visualizes the response of the `/playlist_top_artists/{search_group_name}` endpoint:
the category's top 3 artists (from `artist_top_by_category`), followed by a
"discovery" block of artists similar to those tops, built by favoring candidates
similar to *several* of the 3 top artists (approach 4, see
`controllers.pipeline_playlist_top_artists.build_favored_discovery_artists` in the backend).
"""

import sys
import time as time_mod
from pathlib import Path

import requests

import streamlit as st


# Ensure internal imports from 'src' work smoothly
sys.path.append(str(Path(__file__).resolve().parent.parent.parent / "src"))

from components.card_renderer import show_similar_artists
from components.env_banner import render_env_banner
from components.request_debug import render_request_debug
from components.sidebar import _render_api_url_input
from services.backend_api_client import fetch_playlist_top_artists
from services.bigquery_client import fetch_artists_details_batch
from services.database_service import get_playlist_top_artists_composition

from config import settings
from schemas.playlist_top_artists import TopArtistsSearchGroupNameEnum


DEFAULT_SCORE_NAME = settings.PLAYLIST_TOP_ARTISTS_DEFAULT_SCORE_NAME
DEFAULT_DISCOVERY_SIZE = 7
DEFAULT_FILTER_HAS_BOOKABLE_OFFER_IN_MAIN_CATEGORY = True
DEFAULT_FILTER_MAIN_CATEGORY_MATCHES_SEARCH_GROUP_NAME = True

SEARCH_GROUP_NAMES = [search_group.value for search_group in TopArtistsSearchGroupNameEnum]


def main():
    """Coordinate the execution flow of the playlist top artists page."""
    st.set_page_config(page_title="Playlist Top Artistes", layout="wide")
    st.title("🎼 Proxy de l'API de Recommandation V2 - Playlist Top Artistes")
    st.markdown(
        "Exécutez et testez l'endpoint `playlist_top_artists`, qui renvoie les artistes "
        "tops d'une catégorie ainsi qu'un bloc de découverte d'artistes similaires, en "
        "favorisant les artistes similaires à **plusieurs** des 3 tops."
    )

    with st.sidebar:
        st.header("Paramètres de la Requête")
        api_base_url, proxies, api_token = _render_api_url_input()
        st.divider()

        search_group_name = st.selectbox("Catégorie (search_group_name)", options=SEARCH_GROUP_NAMES)

        filter_has_bookable_offer_in_main_category = st.toggle(
            "✅ Exclure sans offre réservable dans la catégorie principale",
            value=DEFAULT_FILTER_HAS_BOOKABLE_OFFER_IN_MAIN_CATEGORY,
            help=(
                "Si désactivé, les candidats sont gardés même sans offre active réservable "
                "dans leur catégorie principale (ignore `artist_mv.main_search_group_name_has_bookable_offer`). "
                "(Pris en compte uniquement si l'API tourne en local)."
            ),
        )
        filter_main_category_matches_search_group_name = st.toggle(
            "🎯 Exclure si catégorie principale différente de la catégorie demandée",
            value=DEFAULT_FILTER_MAIN_CATEGORY_MATCHES_SEARCH_GROUP_NAME,
            help=(
                "Si activé, un artiste similaire est ignoré si son `main_search_group_name` "
                "(artist_mv) ne correspond pas à la catégorie demandée (`search_group_name`). "
                "(Pris en compte uniquement si l'API tourne en local)."
            ),
        )

        with st.expander("Options avancées"):
            score_name = st.text_input(
                "Score utilisé pour le top (score_name)",
                value=DEFAULT_SCORE_NAME,
                help="Variante de score utilisée pour classer les artistes tops de la catégorie "
                "(pris en compte uniquement si l'API tourne en local).",
            )
            discovery_size = st.number_input(
                "Nombre d'artistes de découverte",
                min_value=1,
                max_value=50,
                value=DEFAULT_DISCOVERY_SIZE,
                help="Nombre d'artistes de découverte retournés après les 3 tops "
                "(pris en compte uniquement si l'API tourne en local).",
            )

        run_fetch = st.button("🚀 Obtenir la playlist", type="primary")

    render_env_banner(api_base_url)

    if run_fetch:
        _fetch_and_display_playlist(
            search_group_name,
            filter_has_bookable_offer_in_main_category=filter_has_bookable_offer_in_main_category,
            filter_main_category_matches_search_group_name=filter_main_category_matches_search_group_name,
            score_name=score_name,
            discovery_size=discovery_size,
            api_base_url=api_base_url,
            proxies=proxies,
            api_token=api_token,
        )


def _resolve_artist_display_name(artist_id: str, artist_details_by_id: dict[str, dict]) -> str:
    """
    Return the human-readable artist name from BigQuery metadata, falling back to ``artist_id``.

    Args:
        artist_id (str): Unique identifier of the artist.
        artist_details_by_id (dict[str, dict]): Mapping of ``artist_id -> artist metadata``.

    Returns:
        str: Display name of the artist.
    """
    artist_details = artist_details_by_id.get(artist_id)
    if not artist_details:
        return artist_id

    return artist_details.get("artist_name", artist_id)


def _render_execution_summary_banner(
    api_response_time: float,
    response_params: dict,
    *,
    filter_has_bookable_offer_in_main_category: bool,
    filter_main_category_matches_search_group_name: bool,
) -> None:
    """
    Render the execution metrics summary bar and any disabled-filter informational notice.

    Args:
        api_response_time (float): Elapsed HTTP round-trip time in seconds.
        response_params (dict): ``params`` dictionary returned by the API response.
        filter_has_bookable_offer_in_main_category (bool): Whether the bookable-offer-in-main-category
            filter was enabled.
        filter_main_category_matches_search_group_name (bool): Whether the main-category-matches-search-group
            filter was enabled.
    """
    st.markdown(
        f"""
        <div style="display: flex; gap: 24px; align-items: center; background-color: #f8f9fa;
        padding: 12px 16px; border-radius: 8px; border: 1px solid #e9ecef; margin-bottom: 16px; color: #1f2937;">
            <div style="font-size: 14px;"><b>⏱ Temps d'exécution :</b> {api_response_time:.2f}s</div>
            <div style="font-size: 14px;"><b>📂 Catégorie :</b> {response_params.get("search_group_name", "N/A")}</div>
            <div style="font-size: 14px;"><b>🧮 Score :</b> {response_params.get("score_name", "N/A")}</div>
            <div style="font-size: 14px;"><b>🔑 Call ID :</b> {response_params.get("call_id", "N/A")}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    disabled_filter_labels = [
        filter_label
        for is_filter_enabled, filter_label in (
            (filter_has_bookable_offer_in_main_category, "offre réservable dans la catégorie principale"),
            (filter_main_category_matches_search_group_name, "catégorie principale = catégorie demandée"),
        )
        if not is_filter_enabled
    ]
    if disabled_filter_labels:
        st.info(f"💡 Filtre(s) désactivé(s) : {', '.join(disabled_filter_labels)}.")


def _build_discovery_composition_table_rows(
    top_artists: list[dict],
    discovery_artists: list[dict],
    artist_details_by_id: dict[str, dict],
) -> list[dict]:
    """
    Build the tabular rows explaining how each discovery artist was ranked across the top artists.

    Args:
        top_artists (list[dict]): Top artist entries with ``artist_id`` and ``category_rank``.
        discovery_artists (list[dict]): Discovery artist entries with ``appearance_count``,
            ``avg_rank``, and ``ranks_by_top_artist``.
        artist_details_by_id (dict[str, dict]): Mapping of ``artist_id -> BigQuery metadata``.

    Returns:
        list[dict]: Formatted row dictionaries ready for ``st.dataframe``.
    """
    column_name_by_top_artist_id = {
        top_artist["artist_id"]: (
            f"rang chez #{top_artist['category_rank']} "
            f"{_resolve_artist_display_name(top_artist['artist_id'], artist_details_by_id)}"
        )
        for top_artist in top_artists
    }

    table_rows = []
    for position, discovery_artist in enumerate(discovery_artists, start=1):
        discovery_artist_id = discovery_artist["artist_id"]
        ranks_by_top_artist = discovery_artist.get("ranks_by_top_artist", {})

        row = {
            "#": position,
            "artiste": _resolve_artist_display_name(discovery_artist_id, artist_details_by_id),
            "artist_id": discovery_artist_id,
            "présent dans X tops": discovery_artist["appearance_count"],
            "rang moyen": discovery_artist["avg_rank"],
        }
        for top_artist_id, column_name in column_name_by_top_artist_id.items():
            row[column_name] = ranks_by_top_artist.get(top_artist_id)

        table_rows.append(row)

    return table_rows


def _render_discovery_composition_details(
    top_artists: list[dict],
    discovery_artists: list[dict],
    artist_details_by_id: dict[str, dict],
) -> None:
    """
    Render the expandable dataframe detailing the overlap and rank of each discovery artist.

    Args:
        top_artists (list[dict]): Top artist entries.
        discovery_artists (list[dict]): Discovery artist entries.
        artist_details_by_id (dict[str, dict]): Mapping of ``artist_id -> BigQuery metadata``.
    """
    with st.expander("📋 Détails de la composition du bloc de découverte", expanded=False):
        st.caption(
            "`#` : position dans le bloc de découverte. "
            "`présent dans X tops` (appearance_count) : nombre de tops dont cet artiste est un similaire. "
            "`rang moyen` (avg_rank) : moyenne des rangs ci-contre (plus bas = plus proche). "
            "Les colonnes `rang chez <top>` donnent son rang de similarité dans la liste de chaque top "
            "(vide s'il n'y figure pas). "
            "Tri : appearance_count décroissant puis avg_rank croissant."
        )
        table_rows = _build_discovery_composition_table_rows(
            top_artists=top_artists,
            discovery_artists=discovery_artists,
            artist_details_by_id=artist_details_by_id,
        )
        st.dataframe(table_rows, use_container_width=True, hide_index=True)


def _fetch_and_display_playlist(
    search_group_name: str,
    *,
    filter_has_bookable_offer_in_main_category: bool,
    filter_main_category_matches_search_group_name: bool,
    score_name: str,
    discovery_size: int,
    api_base_url: str,
    proxies: dict | None,
    api_token: str | None,
) -> None:
    """
    Call the ``playlist_top_artists`` API endpoint, reconstruct its composition, and render the UI.

    Args:
        search_group_name (str): Category to look up (path parameter).
        score_name (str): Scoring variant used to rank the category's top artists.
        discovery_size (int): Number of discovery artists requested.
        filter_has_bookable_offer_in_main_category (bool): Exclude discovery candidates without a confirmed
            bookable offer in their main category (``artist_mv``-backed).
        filter_main_category_matches_search_group_name (bool): Exclude discovery candidates whose main category
            differs from ``search_group_name`` (``artist_mv``-backed).
        api_base_url (str): Base URL of the recommendation API.
        proxies (dict | None): Optional SOCKS5 proxy configuration for VPC tunneling.
        api_token (str | None): Optional API token injected as query param ``?token=``.
    """
    # 1. Execute HTTP request against the Recommendation API
    api_url = f"{api_base_url.rstrip('/')}/playlist_top_artists/{search_group_name}"
    query_params = {
        "score_name": score_name,
        "discovery_size": discovery_size,
        "filter_has_bookable_offer_in_main_category": filter_has_bookable_offer_in_main_category,
        "filter_main_category_matches_search_group_name": filter_main_category_matches_search_group_name,
    }

    with st.spinner("Appel de l'API playlist_top_artists en cours..."):
        start_time = time_mod.time()
        try:
            response_data = fetch_playlist_top_artists(
                api_url,
                query_params,
                proxies=proxies,
                api_token=api_token,
            )
        except requests.exceptions.RequestException as error:
            st.error(f"Erreur lors de l'appel de l'API : {error}")
            if error.response is not None:
                st.json(error.response.json())
            st.stop()
        api_response_time = time_mod.time() - start_time

    render_request_debug(method="GET", url=api_url, query_params=query_params, proxies=proxies)

    # 2. Reconstruct top vs. discovery composition from the database
    response_params = response_data.get("params", {}) or {}
    playlist_artist_ids = response_data.get("playlist_artists", [])
    with st.spinner("Reconstitution de la composition de la playlist depuis la base de données..."):
        top_artists, discovery_artists = get_playlist_top_artists_composition(playlist_artist_ids)

    _render_execution_summary_banner(
        api_response_time=api_response_time,
        response_params=response_params,
        filter_has_bookable_offer_in_main_category=filter_has_bookable_offer_in_main_category,
        filter_main_category_matches_search_group_name=filter_main_category_matches_search_group_name,
    )

    if not top_artists:
        st.warning(
            f"Aucun artiste top trouvé pour la catégorie `{search_group_name}` (table `artist_top_by_category`)."
        )
        return

    # 3. Fetch artist display metadata from BigQuery
    all_artist_ids = {top["artist_id"] for top in top_artists} | {artist["artist_id"] for artist in discovery_artists}
    with st.spinner("Récupération des détails des artistes depuis BigQuery..."):
        artist_details_by_id = fetch_artists_details_batch(list(all_artist_ids))

    # 4. Render top artists carousel
    show_similar_artists(
        similar_artists=[{"artist_id_match": top["artist_id"], "rank": top["category_rank"]} for top in top_artists],
        artist_details_map=artist_details_by_id,
        title="🏆 Artistes tops de la catégorie",
    )

    st.markdown("---")

    if not discovery_artists:
        st.warning("Aucun artiste de découverte n'a été retourné (pas de similaires trouvés pour les tops).")
        return

    # 5. Render discovery artists carousel and composition breakdown table
    show_similar_artists(
        similar_artists=[
            {"artist_id_match": artist["artist_id"], "rank": index + 1}
            for index, artist in enumerate(discovery_artists)
        ],
        artist_details_map=artist_details_by_id,
        title="🔎 Artistes de découverte (favorisent les similaires à plusieurs tops)",
    )

    _render_discovery_composition_details(
        top_artists=top_artists,
        discovery_artists=discovery_artists,
        artist_details_by_id=artist_details_by_id,
    )


if __name__ == "__main__":
    main()

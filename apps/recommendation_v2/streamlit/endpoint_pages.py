"""
Registry of the Streamlit pages, one per Recommendation API V2 endpoint.

Shared by the router (`app.py`) and the home page so that adding an endpoint page
only requires a new entry here.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class EndpointPage:
    path: str
    title: str
    icon: str
    method: str
    endpoint: str
    description: str


HOME_PAGE_PATH = "pages/Home.py"

ENDPOINT_PAGES: list[EndpointPage] = [
    EndpointPage(
        path="pages/Playlist_Recommendation.py",
        title="Playlist Recommandation",
        icon="✨",
        method="POST",
        endpoint="/playlist_recommendation/{user_id}",
        description="Playlist d'offres personnalisée pour un utilisateur (filtres, géolocalisation).",
    ),
    EndpointPage(
        path="pages/Similar_Offers.py",
        title="Offres Similaires",
        icon="🔁",
        method="GET",
        endpoint="/similar_offers/{offer_id}",
        description="Offres similaires à une offre source, avec choix du modèle de retrieval.",
    ),
    EndpointPage(
        path="pages/Offer_Page_Playlists.py",
        title="Playlists Page Offre",
        icon="📚",
        method="GET",
        endpoint="/offer_page_playlists/{offer_id}",
        description="Ensemble des playlists affichées sur la page d'une offre, en un seul appel.",
    ),
    EndpointPage(
        path="pages/Similar_Artists.py",
        title="Artistes Similaires",
        icon="🎵",
        method="GET",
        endpoint="/similar_artists/{artist_id}",
        description="Artistes similaires à un artiste donné.",
    ),
    EndpointPage(
        path="pages/Playlist_Top_Artists.py",
        title="Playlist Top Artistes",
        icon="🎼",
        method="GET",
        endpoint="/playlist_top_artists/{search_group_name}",
        description="Top artistes d'une catégorie suivis d'un bloc découverte d'artistes similaires.",
    ),
]

from dataclasses import dataclass
from enum import StrEnum

from pydantic import BaseModel

from schemas.categories import SearchGroupNameEnum
from schemas.playlist_recommendation import RecommendationMetadata
from schemas.similar_offer import SimilarOfferModelChoices


class AnalyticsPlaylistTypeEnum(StrEnum):
    """
    Playlist type identifier sent to Firebase analytics.

    Originally a legacy-compatible value (before the ``/offer_page_playlists``
    endpoint existed, the client itself decided which "similar offer" playlists to
    build and tagged the resulting analytics events with the
    ``similar_offer_playlist_type`` Firebase event property). It now also encodes
    which retrieval model produced the playlist ("two tower" i.e. coreservation,
    or "graph"), so analytics can distinguish playlists by both scope
    (same/other category) and retrieval strategy.

    Values:
        SAME_CATEGORY_TWO_TOWER: Same-category playlist retrieved with the
            "two tower" (coreservation) model.
        SAME_CATEGORY_GRAPH: Same-category playlist retrieved with the graph model.
        OTHER_CATEGORIES_TWO_TOWER: Cross-category playlist retrieved with the
            "two tower" (coreservation) model.
    """

    SAME_CATEGORY_TWO_TOWER = "sameCategorySimilarOffersTwoTower"
    SAME_CATEGORY_GRAPH = "sameCategorySimilarOffersGraph"
    OTHER_CATEGORIES_TWO_TOWER = "otherCategoriesSimilarOffersTwoTower"


class OfferPlaylistTitleEnum(StrEnum):
    """
    Human-readable label displayed above a playlist on the offer page.

    Which title(s) are actually used for a given offer depends on its
    ``search_group_name`` and is decided by ``build_similar_offer_playlist_configs``
    (``controllers/pipeline_offer_page_playlists.py``) — see ``docs/offer_page_playlists.md``
    for the full rules table. That function is the single source of truth — if it
    changes, update the docs too.

    Values:
        LES_FANS_AIMENT_AUSSI: Same-category playlist (coreservation model). Used
            for every category as the first playlist, whatever the retrieval
            strategy used for the other playlist(s).
        DANS_LA_MEME_CATEGORIE: Same-category playlist (graph model). Used only
            for LIVRES/MUSIQUE, as the second playlist alongside
            ``LES_FANS_AIMENT_AUSSI``.
        CA_PEUT_AUSSI_TE_PLAIRE: Cross-category playlist (coreservation model).
            Used for all categories except LIVRES/MUSIQUE, as the second playlist
            alongside ``LES_FANS_AIMENT_AUSSI``.
    """

    LES_FANS_AIMENT_AUSSI = "Les fans aiment aussi"
    DANS_LA_MEME_CATEGORIE = "Dans la même catégorie"
    CA_PEUT_AUSSI_TE_PLAIRE = "Ça peut aussi te plaire"


@dataclass(frozen=True)
class SimilarOfferPlaylistConfig:
    """
    Internal description of a single "similar offer" playlist to generate.
    """

    title: OfferPlaylistTitleEnum
    analytics_playlist_type: AnalyticsPlaylistTypeEnum
    retrieval_model: SimilarOfferModelChoices
    search_group_names: list[SearchGroupNameEnum]


class OfferPlaylistItem(BaseModel):
    """
    A single titled playlist within an offer page response.

    Attributes:
        title: The human-readable label displayed to the user (e.g. "Les fans aiment aussi").
        analytics_playlist_type: Playlist type used for Firebase analytics, encoding
                       both scope and retrieval model (e.g. "sameCategorySimilarOffersTwoTower").
                       See ``AnalyticsPlaylistTypeEnum`` for details.
        results: Ordered list of offer IDs to display.
        params: Metadata describing how this playlist was generated
                (model, call_id, reco_origin…).
    """

    title: OfferPlaylistTitleEnum
    analytics_playlist_type: AnalyticsPlaylistTypeEnum
    results: list[str]
    params: RecommendationMetadata


class OfferPagePlaylistsResponse(BaseModel):
    """
    Aggregated response for the ``/offer_page_playlists/{offer_id}`` endpoint.

    Returns all recommendation playlists for a given offer page in a single
    round-trip, along with their titles and metadata.  The backend is
    responsible for deciding which playlists to include and what titles to
    use — the client should render them in the order they are provided.

    Attributes:
        offer_id: The identifier of the reference offer this response was built for.
        playlists: Ordered list of playlists to display on the offer page.
        from_cache: True when the entire response was served from a Redis cache hit.
    """

    offer_id: str
    playlists: list[OfferPlaylistItem]
    from_cache: bool = False

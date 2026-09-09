from dataclasses import dataclass
from enum import StrEnum

from pydantic import BaseModel

from schemas.categories import SearchGroupNameEnum
from schemas.playlist_recommendation import RecommendationMetadata
from schemas.similar_offer import SimilarOfferModelChoices


class OfferPlaylistTypeEnum(StrEnum):
    """
    Identifies the composition strategy used to build a given playlist.

    The exact mapping between an offer's ``search_group_name`` and the list of
    playlists (title + type + retrieval model) actually returned is defined in
    ``build_similar_offer_playlist_configs`` (``controllers/pipeline_offer_page_playlists.py``).
    See ``docs/offer_page_playlists.md`` for the full, human-readable rules table.
    That function is the single source of truth — if it changes, update the docs too.

    Values:
        SAME_TYPE: Offers from the same category as the reference offer,
            retrieved with the coreservation model. Used for most categories
            (all except LIVRES/MUSIQUE) as the "Les fans aiment aussi" playlist.
        CROSS_TYPE: Offers from all categories *other than* the reference offer's
            category, retrieved with the coreservation model. Used as the
            "Ça peut aussi te plaire" playlist for most categories.
        SAME_TYPE_CORESERVATION: Same category as the reference offer, retrieved
            with the coreservation model. Used specifically for LIVRES/MUSIQUE as
            the "Les fans aiment aussi" playlist.
        SAME_TYPE_GRAPH: Same category as the reference offer, retrieved with the
            graph model. Used specifically for LIVRES/MUSIQUE as the
            "Dans la même catégorie" playlist.
    """

    SAME_TYPE = "same_type"
    CROSS_TYPE = "cross_type"
    SAME_TYPE_CORESERVATION = "same_type_coreservation"
    SAME_TYPE_GRAPH = "same_type_graph"


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
    """Internal description of a single "similar offer" playlist to generate."""

    title: OfferPlaylistTitleEnum
    playlist_type: OfferPlaylistTypeEnum
    retrieval_model: SimilarOfferModelChoices
    search_group_names: list[SearchGroupNameEnum]


class OfferPlaylistItem(BaseModel):
    """
    A single titled playlist within an offer page response.

    Attributes:
        title: The human-readable label displayed to the user (e.g. "Les fans aiment aussi").
        playlist_type: Internal identifier for the playlist composition strategy
                       (e.g. "same_type", "cross_type", "same_type_graph").
        results: Ordered list of offer IDs to display.
        params: Metadata describing how this playlist was generated
                (model, call_id, reco_origin…).
    """

    title: OfferPlaylistTitleEnum
    playlist_type: OfferPlaylistTypeEnum
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

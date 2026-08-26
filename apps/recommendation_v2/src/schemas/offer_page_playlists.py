from dataclasses import dataclass
from enum import StrEnum

from pydantic import BaseModel

from schemas.categories import SearchGroupNameEnum
from schemas.playlist_recommendation import RecommendationMetadata
from schemas.similar_offer import SimilarOfferModelChoices


class OfferPlaylistTypeEnum(StrEnum):
    SAME_TYPE = "same_type"
    CROSS_TYPE = "cross_type"
    SAME_TYPE_CORESERVATION = "same_type_coreservation"
    SAME_TYPE_GRAPH = "same_type_graph"


class OfferPlaylistTitleEnum(StrEnum):
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

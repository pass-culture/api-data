from datetime import datetime
from enum import Enum

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic.alias_generators import to_camel


class PlaylistCategory(str, Enum):
    ABO_PLATEFORME_VIDEO = "ABO_PLATEFORME_VIDEO"
    ABONNEMENTS_MUSEE = "ABONNEMENTS_MUSEE"
    ABONNEMENTS_SPECTACLE = "ABONNEMENTS_SPECTACLE"
    ACHAT_LOCATION_INSTRUMENT = "ACHAT_LOCATION_INSTRUMENT"
    ARTS_VISUELS = "ARTS_VISUELS"
    AUTRES_MEDIAS = "AUTRES_MEDIAS"
    BIBLIOTHEQUE_MEDIATHEQUE = "BIBLIOTHEQUE_MEDIATHEQUE"
    CARTES_CINEMA = "CARTES_CINEMA"
    CD = "CD"
    CONCERTS_EN_LIGNE = "CONCERTS_EN_LIGNE"
    CONCERTS_EVENEMENTS = "CONCERTS_EVENEMENTS"
    CONCOURS = "CONCOURS"
    CONFERENCES = "CONFERENCES"
    DEPRECIEE = "DEPRECIEE"
    DVD_BLU_RAY = "DVD_BLU_RAY"
    ESCAPE_GAMES = "ESCAPE_GAMES"
    EVENEMENTS_CINEMA = "EVENEMENTS_CINEMA"
    EVENEMENTS_PATRIMOINE = "EVENEMENTS_PATRIMOINE"
    FESTIVALS = "FESTIVALS"
    FESTIVAL_DU_LIVRE = "FESTIVAL_DU_LIVRE"
    JEUX_EN_LIGNE = "JEUX_EN_LIGNE"
    JEUX_PHYSIQUES = "JEUX_PHYSIQUES"
    LIVRES_AUDIO_PHYSIQUES = "LIVRES_AUDIO_PHYSIQUES"
    LIVRES_NUMERIQUE_ET_AUDIO = "LIVRES_NUMERIQUE_ET_AUDIO"
    LIVRES_PAPIER = "LIVRES_PAPIER"
    LUDOTHEQUE = "LUDOTHEQUE"
    MATERIELS_CREATIFS = "MATERIELS_CREATIFS"
    MUSIQUE_EN_LIGNE = "MUSIQUE_EN_LIGNE"
    PARTITIONS_DE_MUSIQUE = "PARTITIONS_DE_MUSIQUE"
    PODCAST = "PODCAST"
    PRATIQUES_ET_ATELIERS_ARTISTIQUES = "PRATIQUES_ET_ATELIERS_ARTISTIQUES"
    PRATIQUE_ARTISTIQUE_EN_LIGNE = "PRATIQUE_ARTISTIQUE_EN_LIGNE"
    PRESSE_EN_LIGNE = "PRESSE_EN_LIGNE"
    RENCONTRES = "RENCONTRES"
    RENCONTRES_EN_LIGNE = "RENCONTRES_EN_LIGNE"
    RENCONTRES_EVENEMENTS = "RENCONTRES_EVENEMENTS"
    SALONS_ET_METIERS = "SALONS_ET_METIERS"
    SEANCES_DE_CINEMA = "SEANCES_DE_CINEMA"
    SPECTACLES_ENREGISTRES = "SPECTACLES_ENREGISTRES"
    SPECTACLES_REPRESENTATIONS = "SPECTACLES_REPRESENTATIONS"
    VIDEOS_ET_DOCUMENTAIRES = "VIDEOS_ET_DOCUMENTAIRES"
    VINYLES = "VINYLES"
    VISITES_CULTURELLES = "VISITES_CULTURELLES"
    VISITES_CULTURELLES_EN_LIGNE = "VISITES_CULTURELLES_EN_LIGNE"


class SearchGroupName(str, Enum):
    ARTS_LOISIRS_CREATIFS = "ARTS_LOISIRS_CREATIFS"
    CARTES_JEUNES = "CARTES_JEUNES"
    CONCERTS_FESTIVALS = "CONCERTS_FESTIVALS"
    EVENEMENTS_EN_LIGNE = "EVENEMENTS_EN_LIGNE"
    CINEMA = "CINEMA"
    FILMS_DOCUMENTAIRES_SERIES = "FILMS_DOCUMENTAIRES_SERIES"
    JEUX_JEUX_VIDEOS = "JEUX_JEUX_VIDEOS"
    LIVRES = "LIVRES"
    MEDIA_PRESSE = "MEDIA_PRESSE"
    MUSEES_VISITES_CULTURELLES = "MUSEES_VISITES_CULTURELLES"
    MUSIQUE = "MUSIQUE"
    RENCONTRES_CONFERENCES = "RENCONTRES_CONFERENCES"
    SPECTACLES = "SPECTACLES"


class PlaylistRequestParams(BaseModel):
    """
    Strict validation schema for incoming HTTP POST payloads.

    This model acts as a gatekeeper, ensuring the frontend sends correctly
    formatted filters. It uses an alias generator to automatically convert
    incoming camelCase JSON (e.g., 'startDate') into Pythonic snake_case
    attributes ('start_date').
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    # --- Temporal Constraints ---
    start_date: datetime | None = None
    end_date: datetime | None = None
    is_event: bool | None = None

    # --- Contextual & Format Constraints ---
    is_duo: bool | None = None
    is_restrained: bool | None = True
    is_digital: bool | None = None

    # --- Financial Constraints ---
    price_max: float | None = None
    price_min: float | None = None

    # --- Categorization Filters ---
    categories: list[PlaylistCategory] | None = None
    # TODO: Replace with actual Subcategory Enum once defined, currently using string for flexibility
    subcategories: list[str] | None = None
    search_group_names: list[SearchGroupName] | None = None

    # --- Granular Classification (GTL) Filters ---
    gtl_ids: list[str] | None = None
    gtl_l1: list[str] | None = None
    gtl_l2: list[str] | None = None
    gtl_l3: list[str] | None = None
    gtl_l4: list[str] | None = None

    # --- Diversification & Orchestration Rules ---
    is_reco_shuffled: bool | None = None
    submixing_feature_dict: dict[str, str] | None = None


class RecommendationMetadata(BaseModel):
    """
    Metadata describing how the recommendation was generated.
    Useful for client-side analytics, A/B testing, and debugging.
    """

    reco_origin: str
    model_origin: str
    call_id: str


class RecommendationResponse(BaseModel):
    """
    The final standard payload returned to the client application.
    Contains the ordered list of offer IDs to display in the UI.
    """

    playlist_recommended_offers: list[str]
    params: RecommendationMetadata

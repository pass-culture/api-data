from datetime import datetime
from typing import Any
from typing import Literal

from pydantic import BaseModel

from core.user_context import GeoLocationSource
from schemas.vertex_prediction_item import ItemOrigin


# Value matched by the GCP Log Sink that routes entries to the past_offer_context BigQuery table
GCP_SINK_EVENT_TYPE = "recommendation_past_offer_context_sink"


class TrackingLabels(BaseModel):
    """GCP Sink Routing Label — determines which BigQuery table receives the entry."""

    event_type: str


class TrackingModelParams(BaseModel):
    """Nested model parameters logged inside context_extra_data — mirrors the v1 model_params structure."""

    description: str


class TrackingRequestExtraData(BaseModel):
    """Request-level context logged once and reused for every offer entry in the call."""

    reco_origin: str
    context: str
    model_params: TrackingModelParams | None
    params_in: dict[str, Any] | None
    offer_origin_ids: str | None


class TrackingUserExtraData(BaseModel):
    """User-level context stored in user_extra_data — typed alternative to a plain dict."""

    user_geolocation_source: GeoLocationSource


class TrackingOfferExtraData(BaseModel):
    """Extra Model & Ranking Scores — nested BigQuery RECORD stored in offer_extra_data."""

    offer_ranking_score: float | None
    offer_ranking_origin: Literal["model", "item_rank"]
    offer_booking_number_last_7_days: int
    offer_booking_number_last_14_days: int
    offer_booking_number_last_28_days: int
    offer_semantic_emb_mean: float | None
    offer_retrieval_algorithm: ItemOrigin | None  # item_origin of the offer (e.g. "user_based", "tops", "graph")
    offer_retrieval_vector_column: str | None  # vector_column_name used for retrieval (e.g. "booking_number_desc")
    offer_retrieval_model_name: str
    offer_retrieval_model_version: str
    offer_ranking_model_name: str
    offer_ranking_model_version: str


class TrackingLogPayload(BaseModel):
    """
    BigQuery-bound log payload schema. Field names mirror PastOfferContext columns
    (models/past_offer_context.py) — changes here require a parallel DB schema update.

    Extra fields not persisted to DB: labels (GCP routing), recommendation_api_version.
    """

    # --- GCP Sink Routing Label ---
    labels: TrackingLabels

    # --- Execution Metadata ---
    call_id: str
    context: str
    context_extra_data: TrackingRequestExtraData
    date: datetime

    # --- User Context & Features ---
    user_id: str
    user_bookings_count: int
    user_clicks_count: int
    user_favorites_count: int
    user_deposit_remaining_credit: float
    user_iris_id: str | None
    user_is_geolocated: bool
    user_latitude: float | None
    user_longitude: float | None
    user_extra_data: TrackingUserExtraData

    # --- Offer Data & Features ---
    offer_id: str
    offer_item_id: str
    offer_user_distance: float | None
    offer_is_geolocated: bool | None
    offer_booking_number: int
    offer_stock_price: float
    offer_category: str
    offer_subcategory_id: str
    offer_item_rank: int
    offer_item_score: float | None
    offer_order: int  # Critical for understanding ranking performance
    offer_venue_id: str | None
    offer_creation_date: datetime | None
    offer_stock_beginning_date: datetime | None

    # --- Extra Model & Ranking Scores ---
    offer_extra_data: TrackingOfferExtraData
    recommendation_api_version: int

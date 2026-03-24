import uuid

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from core.geo import get_iris_id_from_coordinates
from core.ranking import rank_and_sort_offers_with_vertex
from core.retrieval import fetch_similar_items_from_vertex
from core.retrieval import filter_out_already_booked_items
from core.retrieval import resolve_closest_venues_from_items
from core.tracking import log_past_offer_context_to_sink
from core.user_context import UserContext
from models.items import ItemIds
from models.user import EnrichedUser
from schemas.similar_offer import SimilarOfferRequestParams, SimilarOfferResponse


async def generate_similar_offers(
    db: AsyncSession,
    offer_id: str,
    user_id: str | None,
    latitude: float | None,
    longitude: float | None,
    params: SimilarOfferRequestParams,
) -> SimilarOfferResponse:
    """
    Orchestrates the similar offer recommendation pipeline.

    It retrieves offers that are semantically similar to a given input offer.

    Pipeline Stages:
    1. Input Validation: Fetches the input offer to ensure existence and retrieve semantic properties.
    2. Context Building: Builds a UserContext. If user lat/lon is missing but the offer is physical,
       uses the offer's location as reference for spatial queries.
    3. Retrieval: Calls Vertex AI with the input item ID to find similar items.
    4. Filtering: Removes items already booked by the user (if authenticated).
    5. Resolution: Maps items to closest physical venues relative to the unified context coordinates.
    6. Ranking: Re-ranks candidates using a dedicated ranking model context ('similar_offer').
    7. Logging: Logs the results for analytics.
    
    Args:
        db (AsyncSession): Database session.
        offer_id (str): The ID of the reference offer.
        user_id (str | None): The ID of the user (can be None for anonymous calls).
        latitude (float | None): User's latitude.
        longitude (float | None): User's longitude.
        params (SimilarOfferRequestParams): Filtering parameters.

    Returns:
        SimilarOfferResponse: The list of similar offer IDs.
    """
    call_id = str(uuid.uuid4())

    # --- 1. Fetch Input Offer & Validation ---
    input_offer = await db.get(ItemIds, offer_id)
    if not input_offer:
        raise HTTPException(status_code=404, detail="Offer not found")
    
    # --- 2. Context Building ---
    # Determine reference coordinates: User's location > Offer's location > None
    ref_latitude = latitude
    ref_longitude = longitude
    
    if ref_latitude is None or ref_longitude is None:
        if input_offer.venue_latitude is not None and input_offer.venue_longitude is not None:
            ref_latitude = input_offer.venue_latitude
            ref_longitude = input_offer.venue_longitude

    # Fetch user profile if user_id is provided
    db_user = None
    real_user_id = user_id or "guest"
    if user_id:
        db_user = await db.get(EnrichedUser, user_id)

    iris_id = await get_iris_id_from_coordinates(db, ref_latitude, ref_longitude)

    user_context = UserContext.build_from_database_record(
        user_id=real_user_id,
        database_user_record=db_user,
        latitude=ref_latitude,
        longitude=ref_longitude,
        iris_id=iris_id
    )

    # --- 3. Retrieval Phase ---
    vertex_result = await fetch_similar_items_from_vertex(
        user_context=user_context,
        params=params,
        item_id=input_offer.item_id,
        call_id=call_id
    )

    # --- 4. Filtering Phase ---
    candidates = vertex_result.predictions
    if user_id:
         candidates = await filter_out_already_booked_items(
            db=db, candidate_items=candidates, user_id=user_id
        )

    # --- 5. Resolution Phase ---
    resolved_offers = await resolve_closest_venues_from_items(
        db=db, candidate_items=candidates, user_context=user_context
    )

    # --- 6. Ranking Phase ---
    ranked_offers = await rank_and_sort_offers_with_vertex(
        offers=resolved_offers, 
        user_context=user_context, 
        context_name="similar_offer"
    )

    # Cap results (e.g. top 20 similar offers)
    final_offers = ranked_offers[:20]
    final_offer_ids = [str(o.offer_id) for o in final_offers]

    # --- 7. Logging Phase ---
    if user_id:
         log_past_offer_context_to_sink(
            user_context=user_context,
            final_playlist=final_offers,
            params=params,
            call_id=call_id,
            reco_origin="similar_offer",
            context_name=f"similar_offer:{input_offer.item_id}" # Log origin item
        )

    return SimilarOfferResponse(
        results=final_offer_ids,
        params={
            "reco_origin": "similar_offer",
            "model_origin": "similar_offer",
            "call_id": call_id,
            "input_offer_id": offer_id 
        }
    )

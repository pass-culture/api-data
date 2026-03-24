from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.similar_offer import generate_similar_offers
from schemas.playlist_recommendation import CategoryEnum, SubcategoryEnum, SearchGroupNameEnum
from schemas.similar_offer import SimilarOfferRequestParams, SimilarOfferResponse
from services.db import get_database_session

router = APIRouter()


@router.get(
    "/similar_offers/{offer_id}",
    response_model=SimilarOfferResponse,
    summary="Get offers similar to a specific offer",
)
async def get_similar_offers(
    offer_id: Annotated[str, Path(description="The unique identifier of the reference offer.")],
    db: Annotated[AsyncSession, Depends(get_database_session)],
    user_id: Annotated[str | None, Query(description="The user's ID, if authenticated.")] = None,
    latitude: Annotated[float | None, Query(description="The user's GPS latitude.")] = None,
    longitude: Annotated[float | None, Query(description="The user's GPS longitude.")] = None,
    categories: Annotated[list[CategoryEnum] | None, Query(description="Filter by categories.")] = None,
    subcategories: Annotated[list[SubcategoryEnum] | None, Query(description="Filter by subcategories.")] = None,
    search_group_names: Annotated[list[SearchGroupNameEnum] | None, Query(description="Filter by search groups.")] = None,
) -> SimilarOfferResponse:
    """
    Retrieves a list of offers that are semantically similar to the provided `offer_id`.

    The endpoint uses a 'Item-to-Item' similarity search via Vertex AI embeddings.
    If the user is authenticated (`user_id` provided), the results are personalized (e.g. removing
    already booked offers) and ranked according to the user's preferences.

    The user's location is used to resolve the closest venue for physical offers.
    If no user location is provided, the location of the input offer is used as a fallback reference.

    Args:
        offer_id (str): The ID of the offer to find similarities for.
        user_id (str | None): Optional user ID for personalization.
        latitude (float | None): Optional user latitude.
        longitude (float | None): Optional user longitude.
        categories (list[CategoryEnum] | None): Optional category filters.
        subcategories (list[SubcategoryEnum] | None): Optional subcategory filters.
        search_group_names (list[SearchGroupNameEnum] | None): Optional search group filters.
        db (AsyncSession): Database session.

    Returns:
        SimilarOfferResponse: A list of similar offer IDs and metadata.
    """
    
    # Construct business parameters object from query parameters
    params = SimilarOfferRequestParams(
        categories=categories,
        subcategories=subcategories,
        search_group_names=search_group_names
    )

    return await generate_similar_offers(
        db=db,
        offer_id=offer_id,
        user_id=user_id,
        latitude=latitude,
        longitude=longitude,
        params=params
    )


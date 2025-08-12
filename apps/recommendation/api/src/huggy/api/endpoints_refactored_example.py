"""
Example FastAPI endpoints using the refactored service pattern

This demonstrates how much cleaner your API endpoints become with the new architecture
"""

from fastapi import APIRouter, HTTPException
from huggy.schemas.user import UserContext
from huggy.services.container import get_services
from pydantic import BaseModel

router = APIRouter()


class LocationRequest(BaseModel):
    latitude: float
    longitude: float


class UserLocationRequest(LocationRequest):
    user_id: str


class RecommendationRequest(BaseModel):
    user_id: str
    latitude: float
    longitude: float
    limit: int = 50


@router.get("/user/{user_id}/context")
async def get_user_context_endpoint(user_id: str, latitude: float, longitude: float):
    """
    Get user context - compare this to what the original endpoint would look like!
    """
    async with get_services() as services:
        user_service = services.get_user_service()
        return await user_service.get_user_context(user_id, latitude, longitude)


@router.get("/user/{user_id}/profile")
async def get_user_profile_endpoint(user_id: str):
    """Get user profile information"""
    async with get_services() as services:
        user_service = services.get_user_service()
        profile = await user_service.get_user_profile(user_id)
        if not profile:
            raise HTTPException(status_code=404, detail="User profile not found")
        return profile


@router.get("/offer/{offer_id}")
async def get_offer_endpoint(offer_id: str):
    """Get offer details"""
    async with get_services() as services:
        offer_service = services.get_offer_service()
        offer = await offer_service.get_offer_characteristics(offer_id)
        if not offer.found:
            raise HTTPException(status_code=404, detail="Offer not found")
        return offer


@router.post("/offers/bulk")
async def get_offers_bulk_endpoint(offer_ids: list[str]):
    """Get multiple offers efficiently"""
    async with get_services() as services:
        offer_service = services.get_offer_service()
        return await offer_service.bulk_get_offers(offer_ids)


@router.get("/iris/{latitude}/{longitude}")
async def get_iris_from_coordinates_endpoint(latitude: float, longitude: float):
    """Get IRIS region from coordinates"""
    async with get_services() as services:
        iris_service = services.get_iris_service()
        iris_id = await iris_service.get_iris_from_coordinates(latitude, longitude)
        if not iris_id:
            raise HTTPException(status_code=404, detail="No IRIS found for coordinates")
        return {"iris_id": iris_id}


@router.post("/recommendations/filter")
async def filter_recommendations_endpoint(request: RecommendationRequest):
    """
    Example of a complex endpoint that uses multiple services
    This shows how easy it is to compose functionality
    """
    async with get_services() as services:
        user_service = services.get_user_service()
        offer_service = services.get_offer_service()
        non_rec_service = services.get_non_recommendable_offer_service()

        # Get user context
        user_context = await user_service.get_user_context(
            request.user_id, request.latitude, request.longitude
        )

        # For demo purposes, let's say we have some candidate offers
        # In real implementation, this would come from your recommendation algorithm
        candidate_offer_ids = ["offer1", "offer2", "offer3", "offer4", "offer5"]

        # Get offer details
        offers = await offer_service.bulk_get_offers(candidate_offer_ids)

        # Extract item IDs
        item_ids = [
            offer.item_id for offer in offers.values() if offer.found and offer.item_id
        ]

        # Filter out non-recommendable items
        recommendable_items = await non_rec_service.filter_recommendable_items(
            user_context, item_ids
        )

        # Filter offers to only include recommendable ones
        final_offers = [
            offers[offer_id]
            for offer_id in candidate_offer_ids
            if offers[offer_id].found
            and offers[offer_id].item_id in recommendable_items
        ]

        # Apply limit
        final_offers = final_offers[: request.limit]

        return {
            "user_context": user_context,
            "total_candidates": len(candidate_offer_ids),
            "recommendable_count": len(recommendable_items),
            "final_recommendations": final_offers,
        }


@router.get("/user/{user_id}/non-recommendable-count")
async def get_non_recommendable_count_endpoint(user_id: str):
    """Get count of non-recommendable items for a user"""
    async with get_services() as services:
        user_service = services.get_user_service()
        non_rec_service = services.get_non_recommendable_offer_service()

        # Create minimal user context
        user_context = UserContext(
            user_id=user_id,
            age=18,  # Default values
            longitude=None,
            latitude=None,
            found=False,
            iris_id=None,
            is_geolocated=False,
        )

        count = await non_rec_service.get_non_recommendable_count(user_context)
        return {"user_id": user_id, "non_recommendable_count": count}


@router.post("/location/context")
async def get_location_context_endpoint(request: LocationRequest):
    """
    Get comprehensive location context
    Demonstrates composing multiple services for rich data
    """
    async with get_services() as services:
        iris_service = services.get_iris_service()

        # Get current IRIS
        current_iris = await iris_service.get_iris_from_coordinates(
            request.latitude, request.longitude
        )

        # Get nearby IRIS regions
        nearby_iris = await iris_service.find_nearby_iris(
            request.latitude, request.longitude, 5.0
        )

        # Get detailed info about current IRIS
        iris_info = None
        if current_iris:
            iris_info = await iris_service.get_iris_info(current_iris)

        return {
            "coordinates": {
                "latitude": request.latitude,
                "longitude": request.longitude,
            },
            "current_iris": current_iris,
            "iris_info": iris_info,
            "nearby_iris": nearby_iris,
            "is_in_france": current_iris is not None,
        }

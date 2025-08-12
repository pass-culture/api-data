from typing import Optional

from huggy.database.query_builder import GeospatialQueryBuilder
from huggy.database.repository import MaterializedViewRepository
from huggy.models.recommendable_offers_raw import (
    RecommendableOffersRaw,
    RecommendableOffersRawMv,
    RecommendableOffersRawMvOld,
    RecommendableOffersRawMvTmp,
)
from huggy.schemas.item import RecommendableItem
from huggy.schemas.model_selection.model_configuration import QueryOrderChoices
from huggy.schemas.offer import Offer, OfferDistance
from huggy.schemas.user import UserContext
from sqlalchemy import func, literal_column, text
from sqlalchemy.ext.asyncio import AsyncSession


class RecommendableOfferService:
    """Service for handling recommendable offers with clean, readable methods"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = MaterializedViewRepository(
            session,
            RecommendableOffersRaw,
            fallback_tables=[
                RecommendableOffersRawMv,
                RecommendableOffersRawMvOld,
                RecommendableOffersRawMvTmp,
            ],
        )
        self.query_builder = GeospatialQueryBuilder(session)

    async def is_geolocated(
        self, user: UserContext, input_offers: Optional[list[Offer]] = None
    ) -> bool:
        """Check if user or offers have geolocation data"""
        if user and user.is_geolocated:
            return True
        if input_offers:
            return any(offer and offer.is_geolocated for offer in input_offers)
        return False

    def _get_user_location_point(
        self, user: UserContext, input_offers: Optional[list[Offer]] = None
    ):
        """Get user location as a PostGIS point"""
        if user and user.is_geolocated:
            return func.ST_SetSRID(func.ST_Point(user.longitude, user.latitude), 4326)
        elif input_offers:
            # Use first geolocated offer as reference point
            for offer in input_offers:
                if offer and offer.is_geolocated:
                    return func.ST_SetSRID(
                        func.ST_Point(offer.longitude, offer.latitude), 4326
                    )
        return None

    def _build_recommendable_items_cte(self, items: list[RecommendableItem]):
        """Build a CTE for recommendable items with rankings"""
        items_data = [(item.item_id, item.item_rank) for item in items]

        # Use VALUES clause for better performance than multiple UNIONs
        values_clause = ", ".join(
            [f"('{item_id}', {rank})" for item_id, rank in items_data]
        )

        return (
            text(f"""
            SELECT item_id, item_rank::integer as item_rank
            FROM (VALUES {values_clause}) AS t(item_id, item_rank)
        """)
            .columns(
                literal_column("item_id").label("item_id"),
                literal_column("item_rank").label("item_rank"),
            )
            .cte("recommendable_items")
        )

    async def get_nearest_offers(
        self,
        user: UserContext,
        recommendable_items: list[RecommendableItem],
        limit: int = 500,
        input_offers: Optional[list[Offer]] = None,
        query_order: QueryOrderChoices = QueryOrderChoices.ITEM_RANK,
    ) -> list[OfferDistance]:
        """Get nearest offers for given user and recommendable items"""

        if not await self.is_geolocated(user, input_offers):
            return []

        # Get the appropriate table
        offer_table = await self.repository.get_available_model()
        user_point = self._get_user_location_point(user, input_offers)

        if not user_point:
            return []

        # Build recommendable items CTE
        items_cte = self._build_recommendable_items_cte(recommendable_items)

        # Calculate distance to user
        distance_expr = func.ST_Distance(offer_table.venue_geo, user_point, True).label(
            "user_distance"
        )

        # Build the main query step by step
        nearest_offers = (
            self.query_builder.select(
                offer_table.offer_id.label("offer_id"),
                offer_table.item_id.label("item_id"),
                distance_expr,
                offer_table.booking_number.label("booking_number"),
                items_cte.c.item_rank.label("item_rank"),
                offer_table.default_max_distance.label("default_max_distance"),
                offer_table.venue_latitude.label("venue_latitude"),
                offer_table.venue_longitude.label("venue_longitude"),
            )
            .from_table(offer_table)
            .join(items_cte, offer_table.item_id == items_cte.c.item_id)
            .subquery("offers")
        )

        # Add row number partitioned by item
        offer_rank = (
            func.row_number()
            .over(
                partition_by=nearest_offers.c.item_id,
                order_by=nearest_offers.c.user_distance.asc(),
            )
            .label("offer_rank")
        )

        # Create ranking subquery
        ranked_offers = (
            self.query_builder.select(nearest_offers, offer_rank)
            .where(
                func.coalesce(nearest_offers.c.user_distance, 0)
                < nearest_offers.c.default_max_distance
            )
            .subquery("ranked")
        )

        # Determine order
        order_column = self._get_order_column(ranked_offers, query_order)

        # Final query - get best offer per item
        final_query = (
            self.query_builder.select(
                ranked_offers.c.offer_id,
                ranked_offers.c.item_id,
                ranked_offers.c.user_distance,
                ranked_offers.c.venue_latitude,
                ranked_offers.c.venue_longitude,
            )
            .from_table(ranked_offers)
            .where(ranked_offers.c.offer_rank == 1)
            .order_by(order_column)
            .limit(limit)
        )

        # Execute and return results
        results = await final_query.fetch_all()
        return [
            OfferDistance(
                offer_id=row.offer_id,
                item_id=row.item_id,
                user_distance=row.user_distance,
                venue_latitude=row.venue_latitude,
                venue_longitude=row.venue_longitude,
            )
            for row in results
        ]

    def _get_order_column(self, ranked_offers, query_order: QueryOrderChoices):
        """Get the appropriate order column based on query_order choice"""
        order_map = {
            QueryOrderChoices.USER_DISTANCE: ranked_offers.c.user_distance.asc(),
            QueryOrderChoices.BOOKING_NUMBER: ranked_offers.c.booking_number.desc(),
            QueryOrderChoices.ITEM_RANK: ranked_offers.c.item_rank.asc(),
        }
        return order_map.get(query_order, ranked_offers.c.item_rank.asc())

    async def get_offers_by_ids(self, offer_ids: list[str]) -> list[dict]:
        """Get offers by their IDs"""
        offer_table = await self.repository.get_available_model()

        result = await (
            self.query_builder.select(offer_table)
            .where(offer_table.offer_id.in_(offer_ids))
            .fetch_all()
        )

        return [dict(row._mapping) for row in result]

    async def get_offers_in_radius(
        self, latitude: float, longitude: float, radius_km: float, limit: int = 100
    ) -> list[dict]:
        """Get all offers within a radius of a point"""
        offer_table = await self.repository.get_available_model()
        center_point = func.ST_SetSRID(func.ST_Point(longitude, latitude), 4326)

        result = await (
            self.query_builder.select(offer_table)
            .where(
                func.ST_DWithin(
                    offer_table.venue_geo,
                    center_point,
                    radius_km * 1000,  # Convert km to meters
                )
            )
            .limit(limit)
            .fetch_all()
        )

        return [dict(row._mapping) for row in result]

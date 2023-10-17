from typing import Dict, List

from pydantic import parse_obj_as
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.expression import literal_column

from huggy.models.recommendable_offers_raw import RecommendableOffersRaw
from huggy.schemas.recommendable_offer import OfferDistance, RecommendableOfferRawDB
from huggy.schemas.user import UserContext


class RecommendableOffer:
    async def get_nearest_offers(
        self,
        db: AsyncSession,
        user: UserContext,
        recommendable_items_ids: Dict[str, float],
    ) -> List[RecommendableOfferRawDB]:
        offer_table: RecommendableOffersRaw = (
            await RecommendableOffersRaw().get_available_table(db)
        )

        user_distance_condition = []
        user_distance = self.get_st_distance(user, offer_table)
        # If user is geolocated
        # Take all the offers near the user AND non geolocated offers
        if user.is_geolocated:
            user_distance_condition.append(
                or_(
                    user_distance <= offer_table.default_max_distance,
                    offer_table.is_geolocated == False,
                )
            )
        # Else, take only non geolocated offers
        else:
            user_distance_condition.append(offer_table.is_geolocated == False)

        underage_condition = []
        # is_underage_recommendable = True
        if user.age and user.age < 18:
            underage_condition.append(offer_table.is_underage_recommendable)

        offer_rank = (
            func.row_number()
            .over(
                partition_by=offer_table.item_id,
                order_by=and_(user_distance.asc(), offer_table.stock_price.asc()),
            )
            .label("offer_rank")
        )

        nearest_offers_subquery = (
            select(
                offer_table.offer_id.label("offer_id"),
                offer_table.item_id.label("item_id"),
                offer_table.venue_id.label("venue_id"),
                user_distance,
                offer_table.booking_number.label("booking_number"),
                offer_table.stock_price.label("stock_price"),
                offer_table.offer_creation_date.label("offer_creation_date"),
                offer_table.stock_beginning_date.label("stock_beginning_date"),
                offer_table.category.label("category"),
                offer_table.subcategory_id.label("subcategory_id"),
                offer_table.search_group_name.label("search_group_name"),
                offer_table.venue_latitude.label("venue_latitude"),
                offer_table.venue_longitude.label("venue_longitude"),
                offer_table.is_geolocated.label("is_geolocated"),
                offer_rank,
            )
            .where(offer_table.item_id.in_(list(recommendable_items_ids.keys())))
            .where(*user_distance_condition)
            .where(*underage_condition)
            .where(offer_table.stock_price <= user.user_deposit_remaining_credit)
            .subquery()
        )

        results = (
            await db.execute(
                select(nearest_offers_subquery).where(
                    nearest_offers_subquery.c.offer_rank == 1
                )
            )
        ).fetchall()

        return parse_obj_as(List[RecommendableOfferRawDB], results)

    async def get_user_offer_distance(
        self, db: AsyncSession, user: UserContext, offer_list: List[str]
    ) -> List[OfferDistance]:
        offer_table: RecommendableOffersRaw = (
            await RecommendableOffersRaw().get_available_table(db)
        )
        user_distance = self.get_st_distance(user, offer_table)

        results = (
            await db.execute(
                select(
                    offer_table.offer_id.label("offer_id"),
                    user_distance.label("user_distance"),
                ).where(offer_table.offer_id.in_(list(offer_list)))
            )
        ).fetchall()
        return parse_obj_as(List[OfferDistance], results)

    def get_st_distance(self, user: UserContext, offer_table: RecommendableOffersRaw):
        if user.is_geolocated:
            user_point = func.ST_GeographyFromText(
                f"POINT({user.longitude} {user.latitude})"
            )
            return func.ST_Distance(user_point, offer_table.venue_geo).label(
                "user_distance"
            )
        else:
            return literal_column("NULL").label("user_distance")

from typing import Dict, List, Optional

from pydantic import TypeAdapter
from sqlalchemy import String, and_, func, or_, select, text, not_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.expression import literal_column, case
import huggy.schemas.recommendable_offer as r_o
from huggy.models.recommendable_offers_raw import RecommendableOffersRaw
from huggy.schemas.item import RecommendableItem
from huggy.schemas.user import UserContext
import huggy.schemas.offer as o
from huggy.schemas.model_selection.model_configuration import QueryOrderChoices


class RecommendableOffer:
    async def is_geolocated(self, user: UserContext, offer: o.Offer) -> bool:
        if user is not None and user.is_geolocated:
            return True
        if offer is not None and offer.is_geolocated:
            return True
        return False

    async def get_nearest_offers(
        self,
        db: AsyncSession,
        user: UserContext,
        recommendable_items_ids: Dict[str, RecommendableItem],
        limit: int = 250,
        offer: Optional[o.Offer] = None,
        query_order: QueryOrderChoices = QueryOrderChoices.ITEM_RANK,
    ) -> List[r_o.RecommendableOffer]:
        offer_table: RecommendableOffersRaw = (
            await RecommendableOffersRaw().get_available_table(db)
        )

        user_distance_condition = []
        user_distance = self.get_st_distance(user, offer_table, offer=offer)
        # If user is geolocated
        # Take all the offers near the user AND non geolocated offers
        if await self.is_geolocated(user, offer):
            user_distance_condition.append(
                text(
                    " NOT offers.is_geolocated OR ( offers.is_geolocated AND offers.user_distance < offers.default_max_distance ) "
                )
            )
        # Else, take only non geolocated offers
        else:
            user_distance_condition.append(text("NOT offers.is_geolocated"))

        underage_condition = []
        # is_underage_recommendable = True
        if user.age is not None and user.age < 18:
            underage_condition.append(offer_table.is_underage_recommendable)

        recommendable_items = self.get_items(recommendable_items_ids)

        nearest_offers_subquery = (
            select(
                offer_table.offer_id.label("offer_id"),
                offer_table.item_id.label("item_id"),
                offer_table.venue_id.label("venue_id"),
                user_distance,
                offer_table.booking_number.label("booking_number"),
                offer_table.total_offers.label("total_offers"),
                offer_table.default_max_distance.label("default_max_distance"),
                offer_table.stock_price.label("stock_price"),
                offer_table.offer_creation_date.label("offer_creation_date"),
                offer_table.stock_beginning_date.label("stock_beginning_date"),
                offer_table.category.label("category"),
                offer_table.subcategory_id.label("subcategory_id"),
                offer_table.search_group_name.label("search_group_name"),
                offer_table.gtl_id.label("gtl_id"),
                offer_table.gtl_l1.label("gtl_l1"),
                offer_table.gtl_l2.label("gtl_l2"),
                offer_table.gtl_l3.label("gtl_l3"),
                offer_table.gtl_l4.label("gtl_l4"),
                offer_table.venue_latitude.label("venue_latitude"),
                offer_table.venue_longitude.label("venue_longitude"),
                offer_table.is_geolocated.label("is_geolocated"),
                recommendable_items.c.item_rank.label("item_rank"),
            )
            .join(
                recommendable_items,
                offer_table.item_id == recommendable_items.c.item_id,
            )
            .where(offer_table.total_offers == 1)
            .where(*underage_condition)
            .where(offer_table.stock_price <= user.user_deposit_remaining_credit)
            .where(not_(offer_table.is_sensitive))
            .subquery(name="offers")
        )

        rank_subquery = (
            select(nearest_offers_subquery)
            .where(*user_distance_condition)
            .subquery(name="rank")
        )

        if query_order == QueryOrderChoices.USER_DISTANCE:
            order_by = rank_subquery.c.user_distance.asc()
        elif query_order == QueryOrderChoices.BOOKING_NUMBER:
            order_by = rank_subquery.c.booking_number.desc()
        elif query_order == QueryOrderChoices.ITEM_RANK:
            order_by = rank_subquery.c.item_rank.asc()

        results = (
            await db.execute(select(rank_subquery).order_by(order_by).limit(limit))
        ).fetchall()
        return TypeAdapter(List[r_o.RecommendableOffer]).validate_python(results)

    async def get_user_offer_distance(
        self, db: AsyncSession, user: UserContext, offer_list: List[str]
    ) -> List[r_o.OfferDistance]:
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
        return TypeAdapter(List[r_o.OfferDistance]).validate_python(results)

    def get_st_distance(
        self,
        user: UserContext,
        offer_table: RecommendableOffersRaw,
        offer: o.Offer = None,
    ):
        if user is not None and user.is_geolocated:
            user_point = func.ST_GeographyFromText(
                f"POINT({user.longitude} {user.latitude})"
            )
            return func.ST_Distance(user_point, offer_table.venue_geo).label(
                "user_distance"
            )
        elif offer is not None and offer.is_geolocated:
            offer_point = func.ST_GeographyFromText(
                f"POINT({offer.longitude} {offer.latitude})"
            )
            return func.ST_Distance(offer_point, offer_table.venue_geo).label(
                "user_distance"
            )
        else:
            return literal_column("NULL").label("user_distance")

    def get_items(self, recommendable_items_ids: Dict[str, RecommendableItem]):
        arr_sql = ",".join(
            [
                f"('{k}'::VARCHAR, {v.item_rank}::INT)"
                for k, v in recommendable_items_ids.items()
            ]
        )

        return (
            text(
                f"""

                    SELECT s.item_id, s.item_rank
                    FROM unnest(ARRAY[{arr_sql}]) 
                    AS s(item_id VARCHAR, item_rank INT)
            """
            )
            .columns(item_id=String, item_rank=String)
            .cte("ranked_items")
        )

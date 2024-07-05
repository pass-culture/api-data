import typing as t
from typing import List, Optional

import huggy.schemas.offer as o
from huggy.models.recommendable_offers_raw import RecommendableOffersRaw
from huggy.schemas.item import RecommendableItem
from huggy.schemas.model_selection.model_configuration import QueryOrderChoices
from huggy.schemas.user import UserContext
from pydantic import TypeAdapter
from sqlalchemy import Integer, String, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.expression import literal_column


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
        recommendable_items_ids: t.List[RecommendableItem],
        limit: int = 500,
        offer: Optional[o.Offer] = None,
        query_order: QueryOrderChoices = QueryOrderChoices.ITEM_RANK,
    ) -> List[o.OfferDistance]:
        if await self.is_geolocated(user, offer):
            offer_table: RecommendableOffersRaw = (
                await RecommendableOffersRaw().get_available_table(db)
            )
            user_distance = self.get_st_distance(user, offer_table, offer=offer)

            recommendable_items = self.get_items(recommendable_items_ids)

            nearest_offers_subquery = (
                select(
                    offer_table.offer_id.label("offer_id"),
                    offer_table.item_id.label("item_id"),
                    user_distance,
                    offer_table.booking_number.label("booking_number"),
                    recommendable_items.c.item_rank.label("item_rank"),
                    offer_table.default_max_distance.label("default_max_distance"),
                    offer_table.venue_latitude.label("venue_latitude"),
                    offer_table.venue_longitude.label("venue_longitude"),
                )
                .join(
                    recommendable_items,
                    offer_table.item_id == recommendable_items.c.item_id,
                )
                .subquery(name="offers")
            )

            offer_rank = (
                func.row_number()
                .over(
                    partition_by=text("offers.item_id"),
                    order_by=text("offers.user_distance ASC"),
                )
                .label("offer_rank")
            )

            rank_subquery = (
                select(nearest_offers_subquery, offer_rank)
                .where(
                    text(
                        "coalesce(offers.user_distance::float, 0) < offers.default_max_distance "
                    )
                )
                .subquery(name="rank")
            )
            if query_order == QueryOrderChoices.USER_DISTANCE:
                order_by = rank_subquery.c.user_distance.asc()
            elif query_order == QueryOrderChoices.BOOKING_NUMBER:
                order_by = rank_subquery.c.booking_number.desc()
            elif query_order == QueryOrderChoices.ITEM_RANK:
                order_by = rank_subquery.c.item_rank.asc()

            results = (
                await db.execute(
                    select(
                        rank_subquery.c.offer_id,
                        rank_subquery.c.item_id,
                        rank_subquery.c.user_distance,
                        rank_subquery.c.venue_latitude,
                        rank_subquery.c.venue_longitude,
                    )
                    .where(rank_subquery.c.offer_rank == 1)
                    .order_by(order_by)
                    .limit(limit)
                )
            ).fetchall()
            return TypeAdapter(List[o.OfferDistance]).validate_python(results)
        return []

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

    def get_items(self, recommendable_items_ids: t.List[RecommendableItem]):
        arr_sql = ",".join(
            [
                f"('{v.item_id}'::VARCHAR, {v.item_rank}::INT)"
                for v in recommendable_items_ids
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
            .columns(item_id=String, item_rank=Integer)
            .cte("ranked_items")
        )

    async def get_user_offer_distance(
        self, db: AsyncSession, user: UserContext, offer_list: List[str]
    ) -> List[o.OfferDistance]:
        offer_table: RecommendableOffersRaw = (
            await RecommendableOffersRaw().get_available_table(db)
        )
        user_distance = self.get_st_distance(user, offer_table)

        results = (
            await db.execute(
                select(
                    offer_table.offer_id.label("offer_id"),
                    offer_table.item_id.label("item_id"),
                    user_distance.label("user_distance"),
                    offer_table.venue_latitude.label("venue_latitude"),
                    offer_table.venue_longitude.label("venue_longitude"),
                ).where(offer_table.offer_id.in_(list(offer_list)))
            )
        ).fetchall()
        return TypeAdapter(List[o.OfferDistance]).validate_python(results)

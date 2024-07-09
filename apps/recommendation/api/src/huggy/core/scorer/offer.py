import asyncio
import typing as t

import huggy.schemas.item as i
import huggy.schemas.offer as o
import huggy.schemas.playlist_params as pp
import huggy.schemas.recommendable_offer as r_o
import huggy.schemas.user as u
from huggy.core.endpoint.ranking_endpoint import RankingEndpoint
from huggy.core.endpoint.retrieval_endpoint import RetrievalEndpoint
from huggy.crud.non_recommendable_offer import get_non_recommendable_items
from huggy.crud.recommendable_offer import RecommendableOffer as RecommendableOfferDB
from huggy.schemas.model_selection.model_configuration import QueryOrderChoices
from huggy.utils.cloud_logging import logger
from huggy.utils.distance import haversine_distance
from huggy.utils.exception import log_error
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession


class OfferScorer:
    def __init__(
        self,
        user: u.UserContext,
        params_in: pp.PlaylistParams,
        retrieval_endpoints: list[RetrievalEndpoint],
        ranking_endpoint: RankingEndpoint,
        model_params,
        offer: t.Optional[o.Offer] = None,
    ):
        self.user = user
        self.offer = offer
        self.offers = params_in.offers
        self.model_params = model_params
        self.params_in = params_in
        self.retrieval_endpoints = retrieval_endpoints
        self.ranking_endpoint = ranking_endpoint

    async def to_dict(self):
        return {
            "retrievals": [await x.to_dict() for x in self.retrieval_endpoints],
            "ranking": await self.ranking_endpoint.to_dict(),
        }

    async def get_scoring(
        self,
        db: AsyncSession,
        call_id: str,
    ) -> list[r_o.RankedOffer]:
        prediction_items: list[i.RecommendableItem] = []
        endpoints_stats = {}

        # // call
        details_list = await asyncio.gather(
            *[endpoint.model_score() for endpoint in self.retrieval_endpoints]
        )
        for endpoint, out in zip(self.retrieval_endpoints, details_list):
            endpoints_stats[endpoint.endpoint_name] = len(out)
            prediction_items.extend(out)

        logger.debug(
            f"Retrieval: {self.user.user_id}: predicted_items -> {len(prediction_items)}",
            extra={
                "event_name": "retrieval",
                "call_id": call_id,
                "user_id": self.user.user_id,
                "total_items": len(prediction_items),
                "total_endpoints": len(self.retrieval_endpoints),
                "endpoints_stats": endpoints_stats,
            },
        )

        # nothing to score
        if len(prediction_items) == 0:
            return []

        # Transform items in offers
        recommendable_offers = await self.get_recommendable_offers(db, prediction_items)

        logger.debug(
            f"Recommendable Offers: {self.user.user_id}: recommendable_offers -> {len(recommendable_offers)}",
            extra={
                "event_name": "recommendable_offers",
                "call_id": call_id,
                "user_id": self.user.user_id,
                "total_offers": len(recommendable_offers),
            },
        )

        # nothing to score
        if len(recommendable_offers) == 0:
            return []

        recommendable_offers = await self.ranking_endpoint.model_score(
            recommendable_offers=recommendable_offers
        )

        logger.debug(
            f"Ranking Offers: {self.user.user_id}: ranking_endpoint -> {len(recommendable_offers)}",
            extra={
                "event_name": "ranking",
                "call_id": call_id,
                "user_id": self.user.user_id,
                "total_offers": len(recommendable_offers),
            },
        )

        return recommendable_offers

    async def get_recommendable_offers(
        self,
        db: AsyncSession,
        recommendable_items: list[i.RecommendableItem],
    ) -> list[r_o.RecommendableOffer]:
        non_recommendable_items = await get_non_recommendable_items(db, self.user)
        recommendable_items_ids = {
            item.item_id: item
            for item in recommendable_items
            if item.item_id not in non_recommendable_items and item.item_id is not None
        }
        return await self.get_nearest_offers(
            db,
            self.user,
            recommendable_items_ids,
            offer=self.offer,
            query_order=self.model_params.query_order,
        )

    async def get_distance(
        self,
        item: i.RecommendableItem,
        user: u.UserContext,
        offer: o.Offer,
        default_max_distance: int,
    ) -> float:
        # If item is not geolocated then return
        if not item.is_geolocated:
            return None, True
        # Else check user or offer statuses
        if user is not None and user.is_geolocated:
            distance = haversine_distance(
                item.example_venue_latitude,
                item.example_venue_longitude,
                user.latitude,
                user.longitude,
            )

        if offer is not None and offer.is_geolocated:
            distance = haversine_distance(
                item.example_venue_latitude,
                item.example_venue_longitude,
                offer.latitude,
                offer.longitude,
            )
        within_radius = distance <= default_max_distance
        return distance, within_radius

    async def get_nearest_offers(
        self,
        db: AsyncSession,
        user: u.UserContext,
        recommendable_items_ids: dict[str, i.RecommendableItem],
        limit: int = 500,
        offer: t.Optional[o.Offer] = None,
        query_order: QueryOrderChoices = QueryOrderChoices.ITEM_RANK,
    ) -> list[r_o.RecommendableOffer]:
        recommendable_offers = []
        multiple_item_offers = []
        for v in recommendable_items_ids.values():
            if v.total_offers == 1 or not v.is_geolocated:
                user_distance, within_radius = await self.get_distance(
                    v, user, offer, default_max_distance=100_000
                )
                if within_radius:
                    recommendable_offers.append(
                        r_o.RecommendableOffer(
                            offer_id=v.example_offer_id,
                            user_distance=user_distance,
                            venue_latitude=v.example_venue_latitude,
                            venue_longitude=v.example_venue_longitude,
                            **v.dict(),
                        )
                    )
            else:
                multiple_item_offers.append(v)
        try:
            if len(multiple_item_offers) > 0:
                offer_distances = await RecommendableOfferDB().get_nearest_offers(
                    db=db,
                    user=user,
                    recommendable_items_ids=multiple_item_offers,
                    limit=limit,
                    offer=offer,
                    query_order=query_order,
                )
                for found_offers in offer_distances:
                    v = recommendable_items_ids[found_offers.item_id]
                    recommendable_offers.append(
                        r_o.RecommendableOffer(
                            offer_id=found_offers.offer_id,
                            user_distance=found_offers.user_distance,
                            venue_latitude=found_offers.venue_latitude,
                            venue_longitude=found_offers.venue_longitude,
                            **v.dict(),
                        )
                    )

        except ProgrammingError as exc:
            log_error(exc, message="Exception error on get_nearest_offers")
        return recommendable_offers

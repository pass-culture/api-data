import asyncio

import typing as t
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession

from huggy.core.endpoint.ranking_endpoint import RankingEndpoint
from huggy.core.endpoint.retrieval_endpoint import RetrievalEndpoint
from huggy.crud.non_recommendable_offer import get_non_recommendable_items
from huggy.crud.recommendable_offer import RecommendableOffer as RecommendableOfferDB
from huggy.schemas.item import RecommendableItem
from huggy.schemas.playlist_params import PlaylistParams
from huggy.schemas.recommendable_offer import RecommendableOffer
from huggy.schemas.user import UserContext
from huggy.schemas.offer import Offer
from huggy.utils.cloud_logging import logger


class OfferScorer:
    def __init__(
        self,
        user: UserContext,
        params_in: PlaylistParams,
        retrieval_endpoints: List[RetrievalEndpoint],
        ranking_endpoint: RankingEndpoint,
        model_params,
        offer: t.Optional[Offer] = None,
    ):
        self.user = user
        self.offer = offer
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
    ) -> List[RecommendableOffer]:
        prediction_items: List[RecommendableItem] = []
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
        recommendable_items: List[RecommendableItem],
    ) -> List[RecommendableOffer]:
        non_recommendable_items = await get_non_recommendable_items(db, self.user)
        recommendable_items = sorted(
            recommendable_items, key=lambda x: x.item_rank, reverse=False
        )[:250]
        recommendable_items_ids = {
            item.item_id: item
            for item in recommendable_items
            if item.item_id not in non_recommendable_items
        }
        recommendable_offers = await RecommendableOfferDB().get_nearest_offers(
            db,
            self.user,
            recommendable_items_ids,
            offer=self.offer,
            query_order=self.model_params.query_order,
        )
        # add item context
        for x in recommendable_offers:
            x.item_origin = recommendable_items_ids[x.item_id].item_origin
        return recommendable_offers

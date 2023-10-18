import asyncio
import itertools
import random
import time
import typing as t
from concurrent.futures import ProcessPoolExecutor
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
from huggy.utils.cloud_logging import logger


class OfferScorer:
    def __init__(
        self,
        user: UserContext,
        params_in: PlaylistParams,
        retrieval_endpoints: List[RetrievalEndpoint],
        ranking_endpoint: RankingEndpoint,
        model_params,
    ):
        self.user = user
        self.model_params = model_params
        self.params_in = params_in
        self.retrieval_endpoints = retrieval_endpoints
        self.ranking_endpoint = ranking_endpoint

    async def loop_score(self) -> t.List[RecommendableItem]:
        prediction_items: List[RecommendableItem] = []
        endpoints_stats = {}
        for endpoint in self.retrieval_endpoints:
            out = endpoint.model_score()
            endpoints_stats[endpoint.endpoint_name] = len(out)
            prediction_items.extend(out)

        return prediction_items

    async def parallel_score(self):
        loop = asyncio.get_event_loop()
        with ProcessPoolExecutor(len(self.retrieval_endpoints)) as pool:
            tasks = [
                loop.run_in_executor(pool, endpoint.model_score)
                for endpoint in self.retrieval_endpoints
            ]
            results = await asyncio.gather(*tasks)
        return list(itertools.chain.from_iterable(results))

    async def get_scoring(
        self,
        db: AsyncSession,
        call_id,
    ) -> List[RecommendableOffer]:
        if len(self.retrieval_endpoints) > 1:
            prediction_items = await self.parallel_score()
        else:
            prediction_items = await self.loop_score()

        logger.info(
            message=f"Retrieval: {self.user.user_id}: predicted_items -> {len(prediction_items)}",
            extra={
                "event_name": "retrieval",
                "call_id": call_id,
                "user_id": self.user.user_id,
                "total_items": len(prediction_items),
                "total_endpoints": len(self.retrieval_endpoints),
            },
        )

        # nothing to score
        if len(prediction_items) == 0:
            return []

        # Transform items in offers
        recommendable_offers = await self.get_recommendable_offers(db, prediction_items)

        logger.info(
            message=f"Recommendable Offers: {self.user.user_id}: recommendable_offers -> {len(recommendable_offers)}",
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

        recommendable_offers = self.ranking_endpoint.model_score(
            recommendable_offers=recommendable_offers
        )

        logger.info(
            message=f"Ranking Offers: {self.user.user_id}: ranking_endpoint -> {len(recommendable_offers)}",
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

        recommendable_items_ids = {
            item.item_id: item.item_rank
            for item in recommendable_items
            if item.item_id not in non_recommendable_items
        }
        recommendable_offers = await RecommendableOfferDB().get_nearest_offers(
            db, self.user, recommendable_items_ids
        )
        return recommendable_offers

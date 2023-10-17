from typing import List

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

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

    async def get_scoring(
        self,
        db: AsyncSession,
        call_id,
    ) -> List[RecommendableOffer]:
        prediction_items: List[RecommendableItem] = []
        endpoints_stats = {}
        for endpoint in self.retrieval_endpoints:
            out = await endpoint.model_score()
            endpoints_stats[endpoint.endpoint_name] = len(out)
            prediction_items.extend(out)

        logger.info(
            message=f"Retrieval: {self.user.user_id}: predicted_items -> {len(prediction_items)}",
            extra={
                "event_name": "retrieval",
                "call_id": call_id,
                "user_id": self.user.user_id,
                "total_items": len(prediction_items),
                "retrieval_endpoints": endpoints_stats,
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

        recommendable_offers = await self.ranking_endpoint.model_score(
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
        recommendable_offers_db = await RecommendableOfferDB().get_nearest_offers(
            db, self.user, recommendable_items_ids
        )
        recommendable_offers = []
        for ro in recommendable_offers_db:
            recommendable_offers.append(
                RecommendableOffer(
                    item_rank=recommendable_items_ids[ro.item_id], **ro.dict()
                )
            )

        return recommendable_offers

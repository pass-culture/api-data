import asyncio
import typing as t
from dataclasses import dataclass

import huggy.schemas.item as i
import huggy.schemas.offer as o
import huggy.schemas.playlist_params as pp
import huggy.schemas.recommendable_offer as r_o
import huggy.schemas.user as u
from aiocache import Cache
from aiocache.serializers import PickleSerializer
from huggy.core.endpoint.ranking_endpoint import RankingEndpoint
from huggy.core.endpoint.retrieval_endpoint import RetrievalEndpoint
from huggy.crud.non_recommendable_offer import get_non_recommendable_items
from huggy.crud.recommendable_offer import RecommendableOffer as RecommendableOfferDB
from huggy.schemas.model_selection.model_configuration import QueryOrderChoices
from huggy.utils.cloud_logging import logger
from huggy.utils.distance import haversine_distance
from huggy.utils.exception import log_error
from huggy.utils.hash import hash_from_keys
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

OFFER_DB_CACHE = Cache(
    Cache.MEMORY, ttl=3000, serializer=PickleSerializer(), namespace="offer_db_cache"
)
MAX_NEAREST_OFFERS = 500


@dataclass
class RecommendableOfferResult:
    recommendable_offer: list[r_o.RecommendableOffer]


class OfferScorer:
    def __init__(
        self,
        user: u.UserContext,
        params_in: pp.PlaylistParams,
        retrieval_endpoints: list[RetrievalEndpoint],
        ranking_endpoint: RankingEndpoint,
        model_params,
        input_offers: t.Optional[list[o.Offer]] = None,
    ):
        self.user = user
        self.input_offers = input_offers
        self.model_params = model_params
        self.params_in = params_in
        self.retrieval_endpoints = retrieval_endpoints
        self.ranking_endpoint = ranking_endpoint
        self.use_cache = True
        self.offer_cached = False

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
                "offer_cached": self.offer_cached,
                "use_cache": self.use_cache,
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

        result: RecommendableOfferResult = None

        # Attempt to retrieve from cache
        if self.use_cache:
            instance_hash = hash_from_keys(
                {"item_ids": sorted(recommendable_items_ids.keys())}
            )
            cache_key = f"{self.user.iris_id}:{instance_hash}"
            result = await OFFER_DB_CACHE.get(cache_key)

        if result is not None:
            self.offer_cached = True
        else:
            # Compute nearest offers if not found in cache
            result = await self.get_nearest_offers(
                db,
                self.user,
                recommendable_items_ids,
                input_offers=self.input_offers,
                query_order=self.model_params.query_order,
            )
            if self.use_cache and result is not None:
                try:
                    await OFFER_DB_CACHE.set(cache_key, result)
                except Exception as e:
                    logger.error(
                        f"Failed to set cache for {cache_key}: {e}", exc_info=True
                    )

        # Check result and its recommendable_offer attribute
        if (
            result is None
            or not hasattr(result, "recommendable_offer")
            or result.recommendable_offer is None
        ):
            logger.error("Recommendable offers could not be retrieved.")
            return []

        return result.recommendable_offer

    async def get_distance(
        self,
        item: i.RecommendableItem,
        user: u.UserContext,
        default_max_distance: int,
        offer_latitude: t.Optional[float] = None,
        offer_longitude: t.Optional[float] = None,
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

        if offer_latitude is not None and offer_longitude is not None:
            distance = haversine_distance(
                item.example_venue_latitude,
                item.example_venue_longitude,
                offer_latitude,
                offer_longitude,
            )
        within_radius = distance <= default_max_distance
        return distance, within_radius

    async def get_mean_offer_coordinates(
        self, input_offers: t.Optional[list[o.Offer]] = None
    ) -> tuple[t.Optional[float], t.Optional[float]]:
        if input_offers:
            geolocated_offers = [offer for offer in input_offers if offer.is_geolocated]
            if len(geolocated_offers) > 0:
                longitude = sum([offer.longitude for offer in geolocated_offers]) / len(
                    geolocated_offers
                )
                latitude = sum([offer.latitude for offer in geolocated_offers]) / len(
                    geolocated_offers
                )
                return latitude, longitude
        return None, None

    async def get_nearest_offers(
        self,
        db: AsyncSession,
        user: u.UserContext,
        recommendable_items_ids: dict[str, i.RecommendableItem],
        limit: int = MAX_NEAREST_OFFERS,
        input_offers: t.Optional[list[o.Offer]] = None,
        query_order: QueryOrderChoices = QueryOrderChoices.ITEM_RANK,
    ) -> RecommendableOfferResult:
        recommendable_offers = []
        multiple_item_offers = []

        offer_latitude, offer_longitude = await self.get_mean_offer_coordinates(
            input_offers
        )

        for v in recommendable_items_ids.values():
            if v.total_offers == 1 or not v.is_geolocated:
                user_distance, within_radius = await self.get_distance(
                    v,
                    user,
                    default_max_distance=100_000,
                    offer_latitude=offer_latitude,
                    offer_longitude=offer_longitude,
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
                    input_offers=input_offers,
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
        return RecommendableOfferResult(recommendable_offer=recommendable_offers)

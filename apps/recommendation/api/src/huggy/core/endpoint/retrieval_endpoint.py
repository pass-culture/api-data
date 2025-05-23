from abc import abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from fastapi.encoders import jsonable_encoder
from huggy.core.endpoint import VERTEX_CACHE, AbstractEndpoint
from huggy.schemas.item import RecommendableItem
from huggy.schemas.offer import Offer
from huggy.schemas.playlist_params import PlaylistParams
from huggy.schemas.user import UserContext
from huggy.utils.cloud_logging import logger
from huggy.utils.vertex_ai import endpoint_score


@dataclass
class RetrievalPredictionResultItem:
    model_version: str
    model_display_name: str
    recommendable_items: list[RecommendableItem]


def to_datetime(ts):
    try:
        return datetime.fromtimestamp(float(ts))
    except Exception:
        return datetime.fromtimestamp(0.0)


@dataclass
class ListParams:
    label: str
    values: list[str] = None

    def filter(self):
        if self.values is not None and len(self.values) > 0:
            return {self.label: {"$in": self.values}}
        return {}


@dataclass
class RangeParams:
    label: str
    max_val: float = None
    min_val: float = None

    def filter(self):
        if self.min_val is not None and self.max_val is not None:
            return {
                self.label: {"$gte": float(self.min_val), "$lte": float(self.max_val)}
            }
        elif self.min_val is not None:
            return {self.label: {"$gte": float(self.min_val)}}
        elif self.max_val is not None:
            return {self.label: {"$lte": float(self.max_val)}}
        else:
            return {}


@dataclass
class DateParams(RangeParams):
    label: str
    max_val: datetime = None
    min_val: datetime = None

    def filter(self):
        if self.min_val is not None:
            self.min_val = float(self.min_val.timestamp())

        if self.max_val is not None:
            self.max_val = float(self.max_val.timestamp())

        return super().filter()


@dataclass
class EqParams:
    label: str
    value: float = None

    def filter(self):
        if self.value is not None:
            return {self.label: {"$eq": float(self.value)}}
        return {}


class RetrievalEndpoint(AbstractEndpoint):
    """
    Represents an endpoint to retrieve offers.

    Attributes:
        user (UserContext): The user context.
        call_id (str): The call ID.
        params_in (PlaylistParams): The playlist parameters.
        context (str): The context.

    Methods:
        init_input: Initializes the input parameters.
        get_instance: Initializes the payload transmitted to vertexAI endpoint
        model_score: Calculates the model score for recommendable offers.

    """

    def init_input(self, user: UserContext, params_in: PlaylistParams, call_id: str):
        self.user = user
        self.call_id = call_id
        self.params_in = params_in
        self.user_input = str(self.user.user_id)
        self.is_geolocated = self.user.is_geolocated

    @abstractmethod
    def get_instance(self, size):
        pass

    def get_params(self):
        logger.debug(
            f"retrieval_endpoint : params_in {self.endpoint_name}",
            extra=jsonable_encoder(self.params_in),
        )
        params = []

        if not self.is_geolocated:
            params.append(EqParams(label="is_geolocated", value=0.0))

        if self.user.age and self.user.age < 18:
            params.append(EqParams(label="is_underage_recommendable", value=float(1)))

        if self.params_in.is_restrained is not None:
            params.append(EqParams(label="is_restrained", value=float(0)))

        # dates filter
        if self.params_in.start_date is not None or self.params_in.end_date is not None:
            label = (
                "stock_beginning_date"
                if self.params_in.is_event
                else "offer_creation_date"
            )
            params.append(
                DateParams(
                    label=label,
                    min_val=self.params_in.start_date,
                    max_val=self.params_in.end_date,
                )
            )

        # stock_price
        if self.params_in.price_max is not None:
            price_max = min(
                self.user.user_deposit_remaining_credit, self.params_in.price_max
            )
        else:
            price_max = round(self.user.user_deposit_remaining_credit)

        params.append(
            RangeParams(
                label="stock_price",
                min_val=self.params_in.price_min,
                max_val=price_max,
            )
        )
        params.append(ListParams(label="category", values=self.params_in.categories))
        params.append(
            ListParams(
                label="search_group_name", values=self.params_in.search_group_names
            )
        )
        params.append(
            ListParams(label="subcategory_id", values=self.params_in.subcategories)
        )
        params.append(ListParams(label="gtl_id", values=self.params_in.gtl_ids))
        params.append(ListParams(label="gtl_l1", values=self.params_in.gtl_l1))
        params.append(ListParams(label="gtl_l2", values=self.params_in.gtl_l2))
        params.append(ListParams(label="gtl_l3", values=self.params_in.gtl_l3))
        params.append(ListParams(label="gtl_l4", values=self.params_in.gtl_l4))

        params.append(EqParams(label="offer_is_duo", value=self.params_in.is_duo))

        if self.params_in.offer_type_list is not None:
            label, domain = [], []
            for kv in self.params_in.offer_type_list:
                key = kv.get("key", None)
                val = kv.get("value", None)
                if key is not None and val is not None:
                    domain.append(key)
                    label.append(val)
            params.append(ListParams(label="offer_type_domain", values=domain))
            params.append(ListParams(label="offer_type_label", values=label))

        filters = {"$and": {k: v for d in params for k, v in d.filter().items()}}
        logger.debug(
            f"retrieval_endpoint : {self.endpoint_name} filters",
            extra=jsonable_encoder(filters),
        )

        return filters

    async def _vertex_retrieval_score(
        self, instance: dict
    ) -> RetrievalPredictionResultItem:
        prediction_result = await endpoint_score(
            instances=instance,
            endpoint_name=self.endpoint_name,
            fallback_endpoints=self.fallback_endpoints,
        )

        return RetrievalPredictionResultItem(
            model_version=prediction_result.model_version,
            model_display_name=prediction_result.model_display_name,
            recommendable_items=[
                RecommendableItem(
                    item_id=r["item_id"],
                    item_rank=r["idx"],
                    item_score=r.get("_distance", None),
                    item_origin=self.MODEL_TYPE,
                    item_cluster_id=r.get("cluster_id", None),
                    item_topic_id=r.get("topic_id", None),
                    semantic_emb_mean=r.get("semantic_emb_mean", None),
                    is_geolocated=bool(r["is_geolocated"]),
                    booking_number=r["booking_number"],
                    booking_number_last_7_days=r["booking_number_last_7_days"],
                    booking_number_last_14_days=r["booking_number_last_14_days"],
                    booking_number_last_28_days=r["booking_number_last_28_days"],
                    stock_price=r["stock_price"],
                    category=r["category"],
                    subcategory_id=r["subcategory_id"],
                    search_group_name=r["search_group_name"],
                    offer_creation_date=to_datetime(r["offer_creation_date"]),
                    stock_beginning_date=to_datetime(r["stock_beginning_date"]),
                    gtl_id=r["gtl_id"],
                    gtl_l3=r["gtl_l3"],
                    gtl_l4=r["gtl_l4"],
                    total_offers=r["total_offers"],
                    example_offer_id=r["example_offer_id"],
                    example_venue_latitude=r["example_venue_latitude"],
                    example_venue_longitude=r["example_venue_longitude"],
                )
                for r in prediction_result.predictions
            ],
        )

    async def model_score(self) -> list[RecommendableItem]:
        result: RetrievalPredictionResultItem = None
        instance = self.get_instance(self.size)

        # Retrieve cache if exists
        if self.use_cache:
            instance_hash = self._get_instance_hash(instance)
            cache_key = f"{self.endpoint_name}:{instance_hash}"
            result: RetrievalPredictionResultItem = await VERTEX_CACHE.get(cache_key)

        if result is not None:
            self.cached = True
            self._log_cache_usage(cache_key, "Used")
        else:
            # Compute retrieval if cache not found
            result = await self._vertex_retrieval_score(instance)
            if self.use_cache and result is not None:
                try:
                    await VERTEX_CACHE.set(cache_key, result)
                    self._log_cache_usage(cache_key, "Set")
                except Exception as e:
                    logger.error(
                        f"Failed to set cache for {cache_key}: {e}", exc_info=True
                    )

        # Check result before accessing attributes
        if result is None:
            logger.error("Result is None. Unable to proceed.")
            return []

        # Set model version and display name for logging purposes
        self.model_display_name = result.model_display_name
        self.model_version = result.model_version

        return result.recommendable_items

    def _log_cache_usage(self, cache_key: str, action: str) -> None:
        logger.debug(
            f"{action} cache in retrieval_endpoint {cache_key}",
            extra={
                "event_name": "cache_retrieval_endpoint",
                "endpoint_name": self.endpoint_name,
                "hash": cache_key,
            },
        )


class BookingNumberRetrievalEndpoint(RetrievalEndpoint):
    MODEL_TYPE = "tops"

    def get_instance(self, size: int):
        return {
            "model_type": "tops",
            "user_id": str(self.user.user_id),
            "size": size,
            "params": self.get_params(),
            "call_id": self.call_id,
            "debug": 1,
            "vector_column_name": "booking_number_desc",
            "similarity_metric": "dot",
            "re_rank": 0,
        }


class CreationTrendRetrievalEndpoint(RetrievalEndpoint):
    MODEL_TYPE = "tops"

    def get_instance(self, size: int):
        return {
            "model_type": "tops",
            "user_id": str(self.user.user_id),
            "size": size,
            "params": self.get_params(),
            "call_id": self.call_id,
            "debug": 1,
            "vector_column_name": "booking_creation_trend_desc",
            "similarity_metric": "dot",
            "re_rank": 0,
        }


class ReleaseTrendRetrievalEndpoint(RetrievalEndpoint):
    MODEL_TYPE = "tops"

    def get_instance(self, size: int):
        return {
            "model_type": "tops",
            "user_id": str(self.user.user_id),
            "size": size,
            "params": self.get_params(),
            "call_id": self.call_id,
            "debug": 1,
            "vector_column_name": "booking_release_trend_desc",
            "similarity_metric": "dot",
            "re_rank": 0,
        }


class RecommendationRetrievalEndpoint(RetrievalEndpoint):
    MODEL_TYPE = "user_based"

    def get_instance(self, size: int):
        return {
            "model_type": "recommendation",
            "user_id": str(self.user.user_id),
            "size": size,
            "params": self.get_params(),
            "call_id": self.call_id,
            "debug": 1,
            "prefilter": 1,
            "similarity_metric": "dot",
        }


class OfferRetrievalEndpoint(RetrievalEndpoint):
    MODEL_TYPE = "user_based"

    def init_input(
        self,
        user: UserContext,
        input_offers: Optional[list[Offer]],
        params_in: PlaylistParams,
        call_id: str,
    ):
        self.user = user
        self.input_offers = input_offers
        self.call_id = call_id
        self.params_in = params_in
        self.items = [offer.item_id for offer in self.input_offers]
        self.is_geolocated = any(offer.is_geolocated for offer in self.input_offers)

    def get_instance(self, size: int):
        return {
            "model_type": "similar_offer",
            "items": self.items,
            "size": size,
            "params": self.get_params(),
            "call_id": self.call_id,
            "debug": 1,
            "similarity_metric": "l2",
            "prefilter": 1,
            "user_id": str(self.user.user_id),
            "re_rank": 0,
        }


class OfferSemanticRetrievalEndpoint(OfferRetrievalEndpoint):
    MODEL_TYPE = "content_based"

    def get_instance(self, size: int):
        return {
            "model_type": "similar_offer",
            "items": self.items,
            "size": size,
            "params": self.get_params(),
            "call_id": self.call_id,
            "debug": 1,
            "similarity_metric": "l2",
            "prefilter": 1,
        }


class OfferBookingNumberRetrievalEndpoint(OfferRetrievalEndpoint):
    MODEL_TYPE = "tops"

    def get_instance(self, size: int):
        return {
            "model_type": "tops",
            "size": size,
            "params": self.get_params(),
            "call_id": self.call_id,
            "debug": 1,
            "vector_column_name": "booking_number_desc",
            "user_id": str(self.user.user_id),
            "similarity_metric": "dot",
            "re_rank": 0,
        }

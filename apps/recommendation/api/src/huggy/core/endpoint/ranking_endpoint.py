import typing as t
from abc import abstractmethod
from datetime import datetime

from fastapi.encoders import jsonable_encoder

from huggy.core.endpoint import AbstractEndpoint
from huggy.schemas.playlist_params import PlaylistParams
from huggy.schemas.recommendable_offer import RankedOffer, RecommendableOffer
from huggy.schemas.user import UserContext
from huggy.utils.cloud_logging import logger
from huggy.utils.vertex_ai import endpoint_score


def to_days(dt: datetime):
    try:
        if dt is not None:
            return (dt - datetime.now()).days
    except Exception as e:
        pass
    return None


def to_float(x: float = None):
    try:
        if x is not None:
            return float(x)
    except Exception as e:
        pass
    return None


class RankingEndpoint(AbstractEndpoint):
    def init_input(self, user: UserContext, params_in: PlaylistParams, call_id: str):
        self.user = user
        self.user_input = str(self.user.user_id)
        self.call_id = call_id
        self.params_in = params_in

    @abstractmethod
    async def model_score(
        self, recommendable_offers: t.List[RecommendableOffer]
    ) -> t.List[RankedOffer]:
        pass


class ItemRankRankingEndpoint(RankingEndpoint):
    """Returns the list sorted by item_rank ascending."""

    MODEL_ORIGIN = "item_rank"

    async def model_score(
        self, recommendable_offers: t.List[RecommendableOffer]
    ) -> t.List[RankedOffer]:
        ranked_offers = []
        recommendable_offers = sorted(
            recommendable_offers, key=lambda x: x.item_rank, reverse=False
        )
        for idx, row in enumerate(recommendable_offers):
            ranked_offers.append(
                RankedOffer(
                    offer_rank=float(idx),
                    offer_score=None,
                    offer_origin=self.MODEL_ORIGIN,
                    **row.model_dump(),
                )
            )
        logger.debug(
            f"ranking_endpoint {str(self.user.user_id)} out : {len(ranked_offers)}"
        )
        return ranked_offers


class DistanceRankingEndpoint(RankingEndpoint):
    """Returns the list sorted by distance ascending."""

    MODEL_ORIGIN = "distance"

    async def model_score(
        self, recommendable_offers: t.List[RecommendableOffer]
    ) -> t.List[RankedOffer]:
        ranked_offers = []
        recommendable_offers = sorted(
            recommendable_offers, key=lambda x: x.user_distance or 0, reverse=False
        )
        for idx, row in enumerate(recommendable_offers):
            ranked_offers.append(
                RankedOffer(
                    offer_rank=float(idx),
                    offer_score=None,
                    offer_origin=self.MODEL_ORIGIN,
                    **row.model_dump(),
                )
            )
        logger.debug(
            f"ranking_endpoint {str(self.user.user_id)} out : {len(ranked_offers)}"
        )
        return ranked_offers


class ModelRankingEndpoint(RankingEndpoint):
    """Calls LGBM model to sort offers."""

    MODEL_ORIGIN = "model"

    def get_instance(
        self, recommendable_offers: t.List[RecommendableOffer]
    ) -> t.List[t.Dict]:
        offers_list = []
        for row in recommendable_offers:
            offers_list.append(
                {
                    "offer_id": row.offer_id,
                    "offer_subcategory_id": row.subcategory_id,
                    "user_bookings_count": to_float(self.user.bookings_count),
                    "user_clicks_count": to_float(self.user.clicks_count),
                    "user_favorites_count": to_float(self.user.favorites_count),
                    "user_deposit_remaining_credit": to_float(
                        self.user.user_deposit_remaining_credit
                    ),
                    "user_is_geolocated": to_float(self.user.is_geolocated),
                    "user_iris_x": to_float(self.user.longitude),
                    "user_iris_y": to_float(self.user.latitude),
                    "offer_user_distance": to_float(row.user_distance),
                    "offer_booking_number": to_float(row.booking_number),
                    "offer_item_score": to_float(row.item_rank),
                    "offer_is_geolocated": to_float(row.is_geolocated),
                    "offer_stock_price": to_float(row.stock_price),
                    "offer_creation_days": to_days(row.offer_creation_date),
                    "offer_stock_beginning_days": to_days(row.stock_beginning_date),
                }
            )
        return offers_list

    async def model_score(
        self, recommendable_offers: t.List[RecommendableOffer]
    ) -> t.List[RankedOffer]:
        instances = self.get_instance(recommendable_offers)
        prediction_result = await endpoint_score(
            instances=instances, endpoint_name=self.endpoint_name
        )
        self.model_version = prediction_result.model_version
        self.model_display_name = prediction_result.model_display_name
        # sort model output dict
        prediction_dict = {
            str(r["offer_id"]): {"offer_rank": idx, "offer_score": r["score"]}
            for idx, r in enumerate(
                sorted(
                    prediction_result.predictions,
                    key=lambda x: x["score"],
                    reverse=True,
                )
            )
        }
        logger.debug(
            f"ranking_endpoint {str(self.user.user_id)} offers : {len(recommendable_offers)}",
            extra=prediction_dict,
        )

        ranked_offers = []
        not_found = []
        for row in recommendable_offers:
            current_score = prediction_dict.get(str(row.offer_id), {})
            offer_rank = current_score.get("offer_rank", None)
            if offer_rank is not None:
                ranked_offers.append(
                    RankedOffer(
                        offer_rank=offer_rank,
                        offer_score=current_score.get("offer_score", None),
                        offer_origin=self.MODEL_ORIGIN,
                        **row.model_dump(),
                    )
                )
            else:
                not_found.append(row)

        if len(not_found) > 0:
            logger.warn(
                f"ranking_endpoint, offer not found",
                extra=jsonable_encoder(
                    {
                        "event_name": "ranking",
                        "event_details": "offer not found",
                        "user_id": self.user.user_id,
                        "total_not_found": len(not_found),
                        "total_recommendable_offers": len(recommendable_offers),
                        "total_ranked_offers": len(ranked_offers),
                        "not_found": [x.dict() for x in not_found],
                    }
                ),
            )

        logger.debug(
            f"ranking_endpoint {str(self.user.user_id)} out : {len(ranked_offers)}"
        )
        return sorted(ranked_offers, key=lambda x: x.offer_rank, reverse=False)


class NoPopularModelRankingEndpoint(ModelRankingEndpoint):
    """Calls LGBM model to sort offers without booking_number variable."""

    MODEL_ORIGIN = "no_popular_model"

    def get_instance(
        self, recommendable_offers: t.List[RecommendableOffer]
    ) -> t.List[t.Dict]:
        offers_list = []
        for row in recommendable_offers:
            offers_list.append(
                {
                    "offer_id": row.offer_id,
                    "offer_subcategory_id": row.subcategory_id,
                    "user_bookings_count": to_float(self.user.bookings_count),
                    "user_clicks_count": to_float(self.user.clicks_count),
                    "user_favorites_count": to_float(self.user.favorites_count),
                    "user_deposit_remaining_credit": to_float(
                        self.user.user_deposit_remaining_credit
                    ),
                    "user_is_geolocated": to_float(self.user.is_geolocated),
                    "user_iris_x": to_float(self.user.longitude),
                    "user_iris_y": to_float(self.user.latitude),
                    "offer_user_distance": to_float(row.user_distance),
                    "offer_booking_number": 0,  # force this metric at 0.
                    "offer_item_score": to_float(row.item_rank),
                    "offer_is_geolocated": to_float(row.is_geolocated),
                    "offer_stock_price": to_float(row.stock_price),
                    "offer_creation_days": to_days(row.offer_creation_date),
                    "offer_stock_beginning_days": to_days(row.stock_beginning_date),
                }
            )
        return offers_list

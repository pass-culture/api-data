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


class DummyRankingEndpoint(RankingEndpoint):
    """Return the same list"""

    async def model_score(
        self, recommendable_offers: t.List[RecommendableOffer]
    ) -> t.List[RankedOffer]:
        return recommendable_offers


class ModelRankingEndpoint(RankingEndpoint):
    """Calls LGBM model to sort offers"""

    def get_instance(
        self, recommendable_offers: t.List[RecommendableOffer]
    ) -> t.List[RankedOffer]:
        offers_list = []
        for row in recommendable_offers:
            offers_list.append(
                {
                    "offer_id": row.offer_id,
                    "offer_subcategory_id": row.subcategory_id,
                    "user_clicks_count": to_float(self.user.clicks_count),
                    "user_favorites_count": to_float(self.user.favorites_count),
                    "user_deposit_remaining_credit": to_float(
                        self.user.user_deposit_remaining_credit
                    ),
                    "offer_user_distance": to_float(row.user_distance),
                    "offer_booking_number": to_float(row.booking_number),
                    "offer_item_score": to_float(row.item_rank),
                    "offer_stock_price": to_float(row.stock_price),
                    "offer_creation_days": to_days(row.offer_creation_date),
                    "offer_stock_beginning_days": to_days(row.stock_beginning_date),
                    "is_geolocated": to_float(row.is_geolocated),
                    "venue_latitude": to_float(row.venue_latitude),
                    "venue_longitude": to_float(row.venue_longitude),
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
        prediction_dict = {
            str(r["offer_id"]): r["score"] for r in prediction_result.predictions
        }
        logger.info(
            f"ranking_endpoint {str(self.user.user_id)} offers : {len(recommendable_offers)}",
            extra=prediction_dict,
        )

        ranked_offers = []
        not_found = []
        for row in recommendable_offers:
            current_score = prediction_dict.get(str(row.offer_id), None)
            if current_score is not None:
                ranked_offers.append(
                    RankedOffer(
                        offer_score=current_score,
                        offer_output=current_score,
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

        logger.info(
            f"ranking_endpoint {str(self.user.user_id)} out : {len(ranked_offers)}"
        )
        return sorted(ranked_offers, key=lambda x: x.offer_output, reverse=True)

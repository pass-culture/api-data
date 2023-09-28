import time
from datetime import datetime
from abc import abstractmethod
import typing as t

from huggy.schemas.user import User
from huggy.schemas.playlist_params import PlaylistParams
from huggy.schemas.offer import RecommendableOffer

from huggy.core.endpoint import AbstractEndpoint

from huggy.utils.vertex_ai import endpoint_score
from huggy.utils.env_vars import (
    log_duration,
)


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
    def init_input(self, user: User, params_in: PlaylistParams):
        self.user = user
        self.user_input = str(self.user.user_id)
        self.params_in = params_in

    @abstractmethod
    def model_score(
        self, recommendable_offers: t.List[RecommendableOffer]
    ) -> t.List[RecommendableOffer]:
        pass


class DummyRankingEndpoint(RankingEndpoint):
    """Return the same list"""

    def model_score(
        self, recommendable_offers: t.List[RecommendableOffer]
    ) -> t.List[RecommendableOffer]:
        return recommendable_offers


class ModelRankingEndpoint(RankingEndpoint):
    """Calls LGBM model to sort offers"""

    def get_instance(
        self, recommendable_offers: t.List[RecommendableOffer]
    ) -> t.List[RecommendableOffer]:
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

    def model_score(
        self, recommendable_offers: t.List[RecommendableOffer]
    ) -> t.List[RecommendableOffer]:
        start = time.time()
        instances = self.get_instance(recommendable_offers)
        prediction_result = endpoint_score(
            instances=instances, endpoint_name=self.endpoint_name
        )
        log_duration(
            f"ranking_endpoint {str(self.user.user_id)} offers : {len(recommendable_offers)}",
            start,
        )
        self.model_version = prediction_result.model_version
        self.model_display_name = prediction_result.model_display_name
        # smallest = better (indices)
        prediction_dict = {
            r["offer_id"]: r["score"] for r in prediction_result.predictions
        }

        for row in recommendable_offers:
            current_score = prediction_dict.get(row.offer_id, None)
            if current_score is not None:
                row.offer_score = current_score
                row.offer_output = current_score
        log_duration(f"ranking_endpoint {str(self.user.user_id)}", start)
        return sorted(recommendable_offers, key=lambda x: x.offer_output, reverse=True)


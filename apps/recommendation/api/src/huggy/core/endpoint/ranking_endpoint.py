import asyncio
from abc import abstractmethod
from datetime import datetime

from fastapi.encoders import jsonable_encoder
from huggy.core.endpoint import AbstractEndpoint
from huggy.core.endpoint.utils import to_days, to_float, to_int
from huggy.schemas.playlist_params import PlaylistParams
from huggy.schemas.recommendable_offer import RankedOffer, RecommendableOffer
from huggy.schemas.user import UserContext
from huggy.utils.cloud_logging import logger
from huggy.utils.vertex_ai import endpoint_score


class RankingEndpoint(AbstractEndpoint):
    """
    Represents an endpoint for ranking offers based on user preferences.

    Attributes:
        user (UserContext): The user context.
        call_id (str): The call ID.
        params_in (PlaylistParams): The playlist parameters.
        context (str): The context.

    Methods:
        init_input: Initializes the input parameters.
        model_score: Calculates the model score for recommendable offers.

    """

    def init_input(
        self, user: UserContext, params_in: PlaylistParams, call_id: str, context: str
    ):
        self.user = user
        self.user_input = str(self.user.user_id)
        self.call_id = call_id
        self.params_in = params_in
        self.context = context

    @abstractmethod
    async def model_score(
        self, recommendable_offers: list[RecommendableOffer]
    ) -> list[RankedOffer]:
        pass


class ItemRankRankingEndpoint(RankingEndpoint):
    """
    Returns the list sorted by item_rank ascending.

    """

    MODEL_ORIGIN = "item_rank"

    async def model_score(
        self, recommendable_offers: list[RecommendableOffer]
    ) -> list[RankedOffer]:
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
            f"ranking_endpoint {self.user.user_id!s} out : {len(ranked_offers)}"
        )
        return ranked_offers


class DistanceRankingEndpoint(RankingEndpoint):
    """
    Returns the list sorted by distance ascending.

    """

    MODEL_ORIGIN = "distance"

    async def model_score(
        self, recommendable_offers: list[RecommendableOffer]
    ) -> list[RankedOffer]:
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
            f"ranking_endpoint {self.user.user_id!s} out : {len(ranked_offers)}"
        )
        return ranked_offers


class ModelRankingEndpoint(RankingEndpoint):
    """
    Calls LGBM model to sort offers.

    """

    MODEL_ORIGIN = "model"

    @staticmethod
    def batch_events(events, batch_size=200):
        """Batch large predictions."""
        for i in range(0, len(events), batch_size):
            yield events[i : i + batch_size]

    def get_instance(
        self, recommendable_offers: list[RecommendableOffer]
    ) -> list[dict]:
        offers_list = []
        for row in recommendable_offers:
            offers_list.append(
                {
                    "offer_id": row.offer_id,
                    "context": f"{self.context}:{row.item_origin}",
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
                    "offer_booking_number_last_7_days": to_float(
                        row.booking_number_last_7_days
                    ),
                    "offer_booking_number_last_14_days": to_float(
                        row.booking_number_last_14_days
                    ),
                    "offer_booking_number_last_28_days": to_float(
                        row.booking_number_last_28_days
                    ),
                    "offer_semantic_emb_mean": to_float(row.semantic_emb_mean),
                    "offer_item_score": to_float(row.item_score),
                    "offer_item_rank": to_float(row.item_rank),
                    "offer_is_geolocated": to_float(row.new_offer_is_geolocated),
                    "offer_stock_price": to_float(row.new_offer_stock_price),
                    "offer_creation_days": to_days(row.new_offer_creation_days),
                    "offer_stock_beginning_days": to_days(
                        row.new_offer_stock_beginning_days
                    ),
                    "day_of_the_week": to_int(datetime.today().weekday()),
                    "hour_of_the_day": to_int(datetime.now().hour),
                }
            )
        return offers_list

    async def model_score(
        self, recommendable_offers: list[RecommendableOffer]
    ) -> list[RankedOffer]:
        result = await self._get_predictions(recommendable_offers)

        if len(result) > 0:
            ranked_offers = self._rank_offers_by_predictions(
                result, recommendable_offers
            )
        else:
            logger.warn(
                "ranking_endpoint, offer not found",
                extra=jsonable_encoder(
                    {
                        "event_name": "ranking",
                        "event_details": "offer not found",
                        "user_id": self.user.user_id,
                        "total_recommendable_offers": len(recommendable_offers),
                        "total_ranked_offers": 0,
                        "recommendable_offers": recommendable_offers,
                    }
                ),
            )
            ranked_offers = self._rank_offers_fallback(recommendable_offers)

        logger.debug(
            f"ranking_endpoint {self.user.user_id!s} out : {len(ranked_offers)}"
        )
        return sorted(ranked_offers, key=lambda x: x.offer_rank, reverse=False)

    async def _get_predictions(
        self, recommendable_offers: list[RecommendableOffer]
    ) -> list[dict]:
        instances = self.get_instance(recommendable_offers)
        """Retrieve predictions from the model asynchronously."""
        results = await asyncio.gather(
            *[
                endpoint_score(instances=x, endpoint_name=self.endpoint_name)
                for x in list(self.batch_events(instances, batch_size=200))
            ]
        )

        predictions = []
        for prediction_result in results:
            predictions.extend(prediction_result.predictions)
            self.model_version = prediction_result.model_version
            self.model_display_name = prediction_result.model_display_name

        return predictions

    def _rank_offers_by_predictions(
        self, predictions: list, recommendable_offers: list
    ) -> list[RankedOffer]:
        """Rank offers based on the model's predictions."""
        ranked_offers = []

        # Create a dictionary of offer_id -> rank and score
        prediction_dict = {
            str(r["offer_id"]): {"offer_rank": idx, "offer_score": r["score"]}
            for idx, r in enumerate(
                sorted(predictions, key=lambda x: x["score"], reverse=True)
            )
        }

        logger.debug(
            f"ranking_endpoint {self.user.user_id!s} offers : {len(recommendable_offers)}",
            extra=prediction_dict,
        )

        for row in recommendable_offers:
            current_score = prediction_dict.get(str(row.offer_id), {})
            offer_rank = current_score.get("offer_rank")
            if offer_rank is not None:
                ranked_offers.append(
                    RankedOffer(
                        offer_rank=offer_rank,
                        offer_score=current_score.get("offer_score"),
                        offer_origin=self.MODEL_ORIGIN,
                        **row.model_dump(),
                    )
                )

        return ranked_offers

    def _rank_offers_fallback(
        self, recommendable_offers: list[RecommendableOffer]
    ) -> list[RankedOffer]:
        """Rank offers using a fallback method when ranking predictions are not available."""
        recommendable_offers = sorted(
            recommendable_offers, key=lambda x: x.item_rank, reverse=False
        )

        return [
            RankedOffer(
                offer_rank=float(idx),
                offer_score=None,
                offer_origin=self.MODEL_ORIGIN,
                **row.model_dump(),
            )
            for idx, row in enumerate(recommendable_offers)
        ]


class NoPopularModelRankingEndpoint(ModelRankingEndpoint):
    """
    Calls LGBM model to sort offers without booking_number variable.

    """

    MODEL_ORIGIN = "no_popular_model"

    def get_instance(
        self, recommendable_offers: list[RecommendableOffer]
    ) -> list[dict]:
        offers_list = []
        for row in recommendable_offers:
            offers_list.append(
                {
                    "offer_id": row.offer_id,
                    "context": f"{self.context}:{row.item_origin}",
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
                    "offer_booking_number": 0,  # force theses metrics at 0.
                    "offer_booking_number_last_7_days": 0,
                    "offer_booking_number_last_14_days": 0,
                    "offer_booking_number_last_28_days": 0,
                    "offer_semantic_emb_mean": to_float(row.semantic_emb_mean),
                    "offer_item_score": to_float(row.item_score),
                    "offer_item_rank": to_float(row.item_rank),
                    "offer_is_geolocated": to_float(row.is_geolocated),
                    "offer_stock_price": to_float(row.stock_price),
                    "offer_creation_days": to_days(row.offer_creation_date),
                    "offer_stock_beginning_days": to_days(row.stock_beginning_date),
                    "day_of_the_week": to_int(datetime.today().weekday()),
                    "hour_of_the_day": to_int(datetime.now().hour),
                }
            )
        return offers_list

import datetime
from abc import ABC, abstractmethod
from typing import Optional

import huggy.schemas.offer as o
import pytz
from fastapi.encoders import jsonable_encoder
from huggy.core.model_selection.model_configuration.configuration import (
    ForkOut,
)
from huggy.core.scorer.offer import OfferScorer
from huggy.models.past_recommended_offers import PastOfferContext
from huggy.schemas.playlist_params import PlaylistParams
from huggy.schemas.recommendable_offer import RankedOffer
from huggy.schemas.user import UserContext
from huggy.utils.env_vars import NUMBER_OF_RECOMMENDATIONS
from huggy.utils.mixing import order_offers_by_score_and_diversify_features
from sqlalchemy.ext.asyncio import AsyncSession


class ModelEngine(ABC):
    """
    Abstract base class for building the scoring pipeline used in the recommendation system.

    Attributes:
        user (UserContext): Contains user-specific data used for generating personalized recommendations.
        params_in (PlaylistParams): Input parameters defining the playlist or set of offers being processed.
        call_id (str): Unique identifier for the recommendation call session.
        context (str): Additional context regarding the recommendation, such as session data or request origin.
        input_offers (list[o.Offer], optional): List of offer objects to be scored. Defaults to None if no offers are provided.
        reco_origin (str): Indicates the origin of the recommendation. It can be "unknown", "cold_start", or "algo".
        model_origin (str): Identifies the origin of the model used for scoring (e.g., algorithm type).
        model_params (ModelConfiguration): Configuration object containing the model parameters.
        scorer (OfferScorer): Initialized scorer object responsible for evaluating and ranking the offers.

    Methods:
        get_model_configuration(user, params_in):
            Retrieves the model configuration based on user data and playlist parameters.

        get_scorer():
            Initializes the scoring mechanisms (retrieval and ranking) and returns an OfferScorer instance.

        get_scoring():
            Generates and returns a list of offer IDs, scored and ranked, to be presented to the user.

        save_context():
            Saves the current recommendation context, including the offers and user session data, to the database for tracking and auditing.

        log_extra_data():
            Logs any additional data related to the model's execution, such as performance metrics or anomalies, for monitoring and debugging.
    """

    def __init__(
        self,
        user: UserContext,
        params_in: PlaylistParams,
        call_id: str,
        context: str,
        input_offers: Optional[list[o.Offer]] = None,
    ):
        self.user = user
        self.input_offers = input_offers
        self.params_in = params_in
        self.call_id = call_id
        self.context = context
        # Get model (cold_start or algo)
        config = self.get_model_configuration(user, params_in)
        self.reco_origin = config.reco_origin
        self.model_origin = config.model_origin
        self.model_params = config.model_configuration
        self.scorer = self.get_scorer()

    @abstractmethod
    def get_model_configuration(
        self, user: UserContext, params_in: PlaylistParams
    ) -> ForkOut:
        pass

    def get_scorer(self) -> OfferScorer:
        # init user_input
        for endpoint in self.model_params.retrieval_endpoints:
            endpoint.init_input(
                user=self.user, params_in=self.params_in, call_id=self.call_id
            )
        self.model_params.ranking_endpoint.init_input(
            user=self.user,
            params_in=self.params_in,
            call_id=self.call_id,
            context=self.context,
        )
        # get scorer
        return self.model_params.scorer(
            user=self.user,
            params_in=self.params_in,
            model_params=self.model_params,
            retrieval_endpoints=self.model_params.retrieval_endpoints,
            ranking_endpoint=self.model_params.ranking_endpoint,
            input_offers=self.input_offers,
        )

    async def get_scoring(self, db: AsyncSession) -> list[str]:
        """
        Returns a list of offer_id to be send to the user
        Depends of the scorer method.

        """
        scored_offers = await self.scorer.get_scoring(db, self.call_id)
        if len(scored_offers) == 0:
            return []

        diversification_params = self.model_params.get_diversification_params(
            self.params_in
        )

        # apply diversification filter
        if diversification_params.is_active:
            scored_offers = order_offers_by_score_and_diversify_features(
                scored_offers=scored_offers,
                score_column=diversification_params.order_column,
                score_order_ascending=diversification_params.order_ascending,
                shuffle_recommendation=diversification_params.is_reco_shuffled,
                feature=diversification_params.mixing_features,
                nb_reco_display=NUMBER_OF_RECOMMENDATIONS,
                submixing_feature_dict=diversification_params.submixing_feature_dict,
            )

        scoring_size = min(len(scored_offers), NUMBER_OF_RECOMMENDATIONS)
        await self.save_context(
            session=db,
            scored_offers=scored_offers[:scoring_size],
            context=self.context,
            user=self.user,
        )

        return [offer.offer_id for offer in scored_offers][:scoring_size]

    async def save_context(
        self,
        session: AsyncSession,
        scored_offers: list[RankedOffer],
        context: str,
        user: UserContext,
    ) -> None:
        if len(scored_offers) > 0:
            date = datetime.datetime.now(pytz.utc)
            context_extra_data = await self.log_extra_data()
            # add similar offer_id origin input.
            if self.input_offers is not None:
                context_extra_data["offer_origin_ids"] = ":".join(
                    [offer.offer_id for offer in self.input_offers]
                )

            for idx, o in enumerate(scored_offers):
                session.add(
                    PastOfferContext(
                        call_id=self.call_id,
                        context=f"{context}:{o.item_origin}",
                        context_extra_data=context_extra_data,
                        date=date,
                        user_id=user.user_id,
                        user_bookings_count=user.bookings_count,
                        user_clicks_count=user.clicks_count,
                        user_favorites_count=user.favorites_count,
                        user_deposit_remaining_credit=user.user_deposit_remaining_credit,
                        user_iris_id=user.iris_id,
                        user_is_geolocated=user.is_geolocated,
                        user_latitude=None,
                        user_longitude=None,
                        user_extra_data={},
                        offer_user_distance=o.user_distance,
                        offer_is_geolocated=o.is_geolocated,
                        offer_id=o.offer_id,
                        offer_item_id=o.item_id,
                        offer_booking_number=o.booking_number,
                        offer_stock_price=o.stock_price,
                        offer_creation_date=o.offer_creation_date,
                        offer_stock_beginning_date=o.stock_beginning_date,
                        offer_category=o.category,
                        offer_subcategory_id=o.subcategory_id,
                        offer_item_rank=o.item_rank,
                        offer_item_score=o.item_score,
                        offer_order=idx,  # order in the final recommendation output list
                        offer_venue_id=None,
                        offer_extra_data={
                            "offer_ranking_score": o.offer_score,
                            "offer_ranking_origin": o.offer_origin,
                            "offer_booking_number_last_7_days": o.booking_number_last_7_days,
                            "offer_booking_number_last_14_days": o.booking_number_last_14_days,
                            "offer_booking_number_last_28_days": o.booking_number_last_28_days,
                            "offer_semantic_emb_mean": o.semantic_emb_mean,
                        },
                    )
                )
            await session.commit()

    async def log_extra_data(self):
        return jsonable_encoder(
            {
                "reco_origin": self.reco_origin,
                "context": self.context,
                "model_params": await self.model_params.to_dict(),
                "params_in": await self.params_in.to_dict(),
                "scorer": await self.scorer.to_dict(),
            }
        )

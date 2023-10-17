import datetime
import typing as t
from abc import ABC, abstractmethod
from typing import List

import pytz
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from huggy.core.model_selection.model_configuration import ModelConfiguration
from huggy.core.scorer.offer import OfferScorer
from huggy.models.past_recommended_offers import OfferContext
from huggy.schemas.playlist_params import PlaylistParams
from huggy.schemas.recommendable_offer import RankedOffer
from huggy.schemas.user import UserContext
from huggy.utils.env_vars import NUMBER_OF_RECOMMENDATIONS
from huggy.utils.mixing import order_offers_by_score_and_diversify_features


class ModelEngine(ABC):
    def __init__(self, user: UserContext, params_in: PlaylistParams):
        self.user = user
        self.params_in = params_in
        # Get model (cold_start or algo)
        self.model_params = self.get_model_configuration(user, params_in)
        self.scorer = self.get_scorer()

    @abstractmethod
    def get_model_configuration(
        self, user: UserContext, params_in: PlaylistParams
    ) -> ModelConfiguration:
        pass

    def get_scorer(self) -> OfferScorer:
        # init user_input
        for endpoint in self.model_params.retrieval_endpoints:
            endpoint.init_input(user=self.user, params_in=self.params_in)
        self.model_params.ranking_endpoint.init_input(
            user=self.user, params_in=self.params_in
        )
        # get scorer
        return self.model_params.scorer(
            user=self.user,
            params_in=self.params_in,
            model_params=self.model_params,
            retrieval_endpoints=self.model_params.retrieval_endpoints,
            ranking_endpoint=self.model_params.ranking_endpoint,
        )

    def get_scoring(self, db: AsyncSession, call_id) -> List[str]:
        """
        Returns a list of offer_id to be send to the user
        Depends of the scorer method.
        """
        scored_offers = self.scorer.get_scoring(db, call_id)
        if len(scored_offers) == 0:
            return []

        diversification_params = self.model_params.get_diversification_params(
            self.params_in
        )

        # apply diversification filter
        if diversification_params.is_active:
            scored_offers = order_offers_by_score_and_diversify_features(
                offers=scored_offers,
                score_column=diversification_params.order_column,
                score_order_ascending=diversification_params.order_ascending,
                shuffle_recommendation=diversification_params.is_reco_shuffled,
                feature=diversification_params.mixing_features,
                nb_reco_display=NUMBER_OF_RECOMMENDATIONS,
            )

        scoring_size = min(len(scored_offers), NUMBER_OF_RECOMMENDATIONS)
        self.save_context(
            db=db,
            offers=scored_offers,
            call_id=call_id,
            context=self.model_params.name,
            user=self.user,
        )

        return [offer.offer_id for offer in scored_offers][:scoring_size]

    def save_context(
        self,
        db: AsyncSession,
        offers: t.List[RankedOffer],
        call_id: str,
        context: str,
        user: UserContext,
    ) -> None:
        if len(offers) > 0:
            date = datetime.datetime.now(pytz.utc)
            for o in offers:
                db.add(
                    OfferContext(
                        call_id=call_id,
                        context=context,
                        date=date,
                        user_id=user.user_id,
                        user_bookings_count=user.bookings_count,
                        user_clicks_count=user.clicks_count,
                        user_favorites_count=user.favorites_count,
                        user_deposit_remaining_credit=user.user_deposit_remaining_credit,
                        user_iris_id=user.iris_id,
                        user_latitude=None,
                        user_longitude=None,
                        offer_user_distance=o.user_distance,
                        offer_id=o.offer_id,
                        offer_item_id=o.item_id,
                        offer_booking_number=o.booking_number,
                        offer_stock_price=o.stock_price,
                        offer_creation_date=o.offer_creation_date,
                        offer_stock_beginning_date=o.stock_beginning_date,
                        offer_category=o.category,
                        offer_subcategory_id=o.subcategory_id,
                        offer_item_score=o.item_rank,
                        offer_order=o.offer_score,
                        offer_venue_id=o.venue_id,
                    )
                )
            db.commit()

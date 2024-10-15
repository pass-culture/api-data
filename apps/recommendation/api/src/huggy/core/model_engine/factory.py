from dataclasses import dataclass
from typing import Optional

import huggy.schemas.offer as o
from huggy.core.model_engine import ModelEngine
from huggy.core.model_engine.recommendation import Recommendation
from huggy.core.model_engine.similar_offer import SimilarOffer
from huggy.schemas.playlist_params import PlaylistParams
from huggy.schemas.user import UserContext
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class ModelEngineOut:
    model: ModelEngine
    results: list[str]


class ModelEngineFactory:
    """
    Factory for creating the appropriate model engine handler.
    """

    @staticmethod
    async def handle_prediction(
        db: AsyncSession,
        user: UserContext,
        params_in: PlaylistParams,
        call_id: str,
        context: str,
        *,
        use_fallback: bool,
        input_offers: Optional[list[o.Offer]] = None,
    ) -> ModelEngineOut:
        """
        Returns the appropriate model engine based on input context and offers.
        Fallback to default recommendation if no results are found or specific conditions apply.
        """
        input_offers = input_offers or []

        model_engine = ModelEngineFactory._determine_model_engine(
            user, params_in, call_id, context, input_offers
        )

        # Get results from the selected model engine
        results = await model_engine.get_scoring(db)

        # Handle fallback scenario if enabled and no results are found
        if use_fallback and len(results) == 0:
            model_engine = await ModelEngineFactory._handle_fallback(
                user, params_in, call_id, input_offers
            )
            results = await model_engine.get_scoring(db)

        return ModelEngineOut(model=model_engine, results=results)

    @staticmethod
    def _determine_model_engine(
        user: UserContext,
        params_in: PlaylistParams,
        call_id: str,
        context: str,
        input_offers: Optional[list[o.Offer]],
    ) -> ModelEngine:
        """
        Determines the appropriate model engine based on the context and input offers.
        """
        if context == "similar_offer":
            return ModelEngineFactory._get_similar_offer_model(
                user, params_in, call_id, input_offers
            )
        elif context == "recommendation":
            return ModelEngineFactory._get_recommendation_model(
                user, params_in, call_id, input_offers
            )
        else:
            raise Exception(f"context {context} is not available")

    @staticmethod
    def _get_similar_offer_model(
        user: UserContext,
        params_in: PlaylistParams,
        call_id: str,
        input_offers: Optional[list[o.Offer]],
    ) -> ModelEngine:
        """
        Selects a model engine for the 'similar_offer' context.
        """
        if input_offers:
            if any(offer.is_sensitive for offer in input_offers):
                return Recommendation(
                    user=user,
                    params_in=params_in,
                    call_id=call_id,
                    context="recommendation_fallback",
                )
            else:
                return SimilarOffer(
                    user=user,
                    params_in=params_in,
                    call_id=call_id,
                    context="similar_offer",
                    input_offers=input_offers,
                )
        else:
            return Recommendation(
                user=user,
                params_in=params_in,
                call_id=call_id,
                context="recommendation_fallback",
            )

    @staticmethod
    def _get_recommendation_model(
        user: UserContext,
        params_in: PlaylistParams,
        call_id: str,
        input_offers: Optional[list[o.Offer]],
    ) -> ModelEngine:
        """
        Selects a model engine for the 'recommendation' context.
        """
        if input_offers:
            return SimilarOffer(
                user=user,
                params_in=params_in,
                call_id=call_id,
                context="hybrid_recommendation",
                input_offers=input_offers,
            )
        else:
            return Recommendation(
                user=user,
                params_in=params_in,
                call_id=call_id,
                context="recommendation",
            )

    @staticmethod
    async def _handle_fallback(
        user: UserContext,
        params_in: PlaylistParams,
        call_id: str,
        input_offers: Optional[list[o.Offer]],
    ) -> ModelEngine:
        """
        Handles fallback by using the 'recommendation_fallback' model.
        """
        fallback_model = Recommendation(
            user=user,
            params_in=params_in,
            call_id=call_id,
            context="recommendation_fallback",
            input_offers=input_offers,
        )
        return fallback_model

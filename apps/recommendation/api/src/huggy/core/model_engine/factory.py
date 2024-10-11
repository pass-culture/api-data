from typing import Optional

import huggy.schemas.offer as o
from huggy.core.model_engine import ModelEngine
from huggy.core.model_engine.recommendation import Recommendation
from huggy.core.model_engine.similar_offer import SimilarOffer
from huggy.schemas.playlist_params import PlaylistParams
from huggy.schemas.user import UserContext
from sqlalchemy.ext.asyncio import AsyncSession


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
        if input_offers is None:
            input_offers = []

        model_engine = None

        # Determine which model to use based on offers and context
        if any(offer.is_sensitive for offer in input_offers):
            model_engine = Recommendation(
                user=user,
                params_in=params_in,
                call_id=call_id,
                context="recommendation",
                input_offers=input_offers,
            )
        elif input_offers and context == "recommendation":
            model_engine = SimilarOffer(
                user=user,
                params_in=params_in,
                call_id=call_id,
                context="hybrid_recommendation",
                input_offers=input_offers,
            )
        elif input_offers:
            model_engine = SimilarOffer(
                user=user,
                params_in=params_in,
                call_id=call_id,
                context="similar_offer",
                input_offers=input_offers,
            )
        else:
            model_engine = Recommendation(
                user=user,
                params_in=params_in,
                call_id=call_id,
                context="recommendation",
                input_offers=input_offers,
            )

        # Get results from the selected model engine
        results = await model_engine.get_scoring(db)

        # Handle fallback scenario if enabled and no results are found
        if use_fallback and not results:
            model_engine = Recommendation(
                user=user,
                params_in=params_in,
                call_id=call_id,
                context="recommendation_fallback",
                input_offers=input_offers,
            )
            results = await model_engine.get_scoring(db)

        return ModelEngineOut(model=model_engine, results=results)

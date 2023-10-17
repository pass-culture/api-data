import datetime
from typing import List

import pytz

from huggy.core.model_engine import ModelEngine
from huggy.core.model_selection import select_sim_model_params
from huggy.core.model_selection.model_configuration import ModelConfiguration
from huggy.models.past_recommended_offers import PastSimilarOffers
from huggy.schemas.offer import Offer
from huggy.schemas.playlist_params import PlaylistParams
from huggy.schemas.user import UserContext


class SimilarOffer(ModelEngine):
    def __init__(self, user: UserContext, offer: Offer, params_in: PlaylistParams):
        self.offer = offer
        super().__init__(user=user, params_in=params_in)

    async def get_model_configuration(
        self, user: UserContext, params_in: PlaylistParams
    ) -> ModelConfiguration:
        model_params, reco_origin = select_sim_model_params(
            params_in.model_endpoint, offer=self.offer
        )
        self.reco_origin = reco_origin
        return model_params

    async def get_scorer(self):
        # init input
        for endpoint in self.model_params.retrieval_endpoints:
            endpoint.init_input(
                user=self.user, offer=self.offer, params_in=self.params_in
            )
        self.model_params.ranking_endpoint.init_input(
            user=self.user, params_in=self.params_in
        )
        return await self.model_params.scorer(
            user=self.user,
            params_in=self.params_in,
            model_params=self.model_params,
            retrieval_endpoints=self.model_params.retrieval_endpoints,
            ranking_endpoint=self.model_params.ranking_endpoint,
        )

    async def get_scoring(self, db: AsyncSession, call_id) -> List[str]:
        if self.offer.item_id is None:
            return []
        return await super().get_scoring(db, call_id)

    async def save_recommendation(
        self, db: AsyncSession, recommendations, call_id
    ) -> None:
        if len(recommendations) > 0:
            date = datetime.datetime.now(pytz.utc)
            for reco in recommendations:
                reco_offer = PastSimilarOffers(
                    user_id=self.user.user_id,
                    origin_offer_id=self.offer.offer_id,
                    offer_id=reco,
                    date=date,
                    group_id=self.model_params.name,
                    model_name=self.scorer.retrieval_endpoints[0].model_display_name,
                    model_version=self.scorer.retrieval_endpoints[0].model_version,
                    call_id=call_id,
                    venue_iris_id=self.offer.iris_id,
                )
                await db.add(reco_offer)
            await db.commit()

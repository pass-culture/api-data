import datetime
import typing as t
from typing import List

import pytz
from sqlalchemy.ext.asyncio import AsyncSession

import huggy.schemas.offer as o
from huggy.core.model_engine import ModelEngine
from huggy.core.model_selection import select_sim_model_params
from huggy.core.model_selection.model_configuration.configuration import ForkOut
from huggy.models.past_recommended_offers import PastSimilarOffers
from huggy.schemas.playlist_params import PlaylistParams
from huggy.schemas.user import UserContext


class SimilarOffer(ModelEngine):
    def get_model_configuration(
        self, user: UserContext, params_in: PlaylistParams
    ) -> ForkOut:
        return select_sim_model_params(params_in.model_endpoint, offer=self.offer)

    def get_scorer(self):
        # init input
        for endpoint in self.model_params.retrieval_endpoints:
            endpoint.init_input(
                user=self.user,
                offer=self.offer,
                params_in=self.params_in,
                call_id=self.call_id,
            )
        self.model_params.ranking_endpoint.init_input(
            user=self.user,
            params_in=self.params_in,
            call_id=self.call_id,
            context=self.context,
        )
        return self.model_params.scorer(
            user=self.user,
            params_in=self.params_in,
            model_params=self.model_params,
            retrieval_endpoints=self.model_params.retrieval_endpoints,
            ranking_endpoint=self.model_params.ranking_endpoint,
            offer=self.offer,
        )

    async def get_scoring(self, db: AsyncSession) -> List[str]:
        if self.offer is not None and self.offer.item_id is None:
            return []
        return await super().get_scoring(db)

    async def save_recommendation(
        self, session: AsyncSession, recommendations: t.List[str]
    ) -> None:
        playlist_type = self.params_in.playlist_type()
        if len(recommendations) > 0:
            date = datetime.datetime.now(pytz.utc)

            for reco in recommendations:
                reco_offer = PastSimilarOffers(
                    user_id=int(self.user.user_id),
                    origin_offer_id=int(self.offer.offer_id),
                    offer_id=int(reco),
                    date=date,
                    group_id=playlist_type,
                    model_name=self.model_params.name,
                    model_version=self.scorer.retrieval_endpoints[0].model_version,
                    call_id=self.call_id,
                    venue_iris_id=self.offer.iris_id,
                    reco_filters=await self.log_extra_data(),
                )
                session.add(reco_offer)
            await session.commit()

from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from huggy.core.model_engine import ModelEngine
from huggy.core.model_selection import select_sim_model_params
from huggy.core.model_selection.model_configuration.configuration import ForkOut
from huggy.schemas.playlist_params import PlaylistParams
from huggy.schemas.user import UserContext


class SimilarOffer(ModelEngine):
    def get_model_configuration(
        self, user: UserContext, params_in: PlaylistParams
    ) -> ForkOut:
        return select_sim_model_params(
            params_in.model_endpoint, offer=self.offer, offers=params_in.offers
        )

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
        if len(self.offers) > 0 and len([offer.item_id for offer in self.offers]) == 0:
            return []
        return await super().get_scoring(db)

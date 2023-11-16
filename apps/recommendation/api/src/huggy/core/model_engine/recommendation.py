import datetime
import typing as t

import pytz
from sqlalchemy.ext.asyncio import AsyncSession

from huggy.core.model_engine import ModelEngine
from huggy.core.model_selection import select_reco_model_params
from huggy.core.model_selection.model_configuration import ModelConfiguration
from huggy.models.past_recommended_offers import PastRecommendedOffers
from huggy.schemas.playlist_params import PlaylistParams
from huggy.schemas.user import UserContext


class Recommendation(ModelEngine):
    def get_model_configuration(
        self, user: UserContext, params_in: PlaylistParams
    ) -> ModelConfiguration:
        model_params, reco_origin = select_reco_model_params(
            params_in.model_endpoint, user
        )
        self.reco_origin = reco_origin
        return model_params

    async def save_recommendation(
        self, session: AsyncSession, recommendations: t.List[str]
    ) -> None:
        if len(recommendations) > 0:
            date = datetime.datetime.now(pytz.utc)

            playlist_type = self.params_in.playlist_type()

            for reco in recommendations:
                reco_offer = PastRecommendedOffers(
                    userid=int(self.user.user_id),
                    offerid=int(reco),
                    date=date,
                    group_id=playlist_type,
                    reco_origin=self.reco_origin,
                    model_name=self.model_params.name,
                    model_version=self.scorer.retrieval_endpoints[0].model_version,
                    call_id=self.call_id,
                    user_iris_id=self.user.iris_id,
                    reco_filters=await self.log_extra_data(),
                )
                session.add(reco_offer)
            await session.commit()

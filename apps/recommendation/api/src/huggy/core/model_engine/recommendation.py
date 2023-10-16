from sqlalchemy.orm import Session
import datetime
import pytz

from huggy.schemas.user import UserContext
from huggy.schemas.playlist_params import PlaylistParams

from huggy.models.past_recommended_offers import PastRecommendedOffers

from huggy.core.model_engine import ModelEngine
from huggy.core.model_selection.model_configuration import ModelConfiguration
from huggy.core.model_selection import (
    select_reco_model_params,
)


class Recommendation(ModelEngine):
    def get_model_configuration(
        self, user: UserContext, params_in: PlaylistParams
    ) -> ModelConfiguration:
        model_params, reco_origin = select_reco_model_params(
            params_in.model_endpoint, user
        )
        self.reco_origin = reco_origin
        return model_params

    def save_recommendation(self, db: Session, recommendations, call_id) -> None:
        if len(recommendations) > 0:
            date = datetime.datetime.now(pytz.utc)
            for reco in recommendations:
                reco_offer = PastRecommendedOffers(
                    userid=self.user.user_id,
                    offerid=reco,
                    date=date,
                    group_id=self.model_params.name,
                    reco_origin=self.reco_origin,
                    model_name=self.scorer.retrieval_endpoints[0].model_display_name,
                    model_version=self.scorer.retrieval_endpoints[0].model_version,
                    call_id=call_id,
                    user_iris_id=self.user.iris_id,
                )
                db.add(reco_offer)
            db.commit()

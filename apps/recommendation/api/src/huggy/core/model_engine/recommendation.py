from huggy.core.model_engine import ModelEngine
from huggy.core.model_selection import select_reco_model_params
from huggy.core.model_selection.model_configuration.configuration import (
    ForkOut,
)
from huggy.schemas.playlist_params import PlaylistParams
from huggy.schemas.user import UserContext


class Recommendation(ModelEngine):
    def get_model_configuration(
        self, user: UserContext, params_in: PlaylistParams
    ) -> ForkOut:
        return select_reco_model_params(params_in.model_endpoint, user)

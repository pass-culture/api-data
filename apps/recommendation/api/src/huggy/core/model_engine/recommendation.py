from huggy.core.model_engine import ModelEngine
from huggy.core.model_selection import select_reco_model_params
from huggy.core.model_selection.model_configuration.configuration import (
    ForkOut,
)
from huggy.schemas.playlist_params import PlaylistParams
from huggy.schemas.user import UserContext


class Recommendation(ModelEngine):
    """
    Class to build the recommendation scoring pipeline.

    1. Get the model endpoint based on the user interaction
    2. Initialize endpoints (retrieval and ranking)
    3. Initialize scorer
    4. Compute scored offers
        a. Get the scored items via retrieval endpoint
        b. Transform items in offers depending on recommendability
        c. Rank offers
    4. Save context in past_offer_context

    """

    def get_model_configuration(
        self, user: UserContext, params_in: PlaylistParams
    ) -> ForkOut:
        return select_reco_model_params(params_in.model_endpoint, user)

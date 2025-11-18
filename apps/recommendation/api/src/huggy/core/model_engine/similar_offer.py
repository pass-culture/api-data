from huggy.core.model_engine import ModelEngine
from huggy.core.model_selection import select_sim_model_params
from huggy.core.model_selection.model_configuration.configuration import ForkOut
from huggy.schemas.playlist_params import PlaylistParams
from huggy.schemas.user import UserContext


class SimilarOffer(ModelEngine):
    """
    Class to build the similar offer scoring pipeline.

    1. Get the model endpoint based on the offer interaction
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
        return select_sim_model_params(
            params_in.model_endpoint, input_offers=self.input_offers
        )

    def get_scorer(self):
        # init input
        selected_retrieval_endpoints = []

        for endpoint in self.model_params.retrieval_endpoints:
            if self.params_in.search_group_names == "LIVRES":
                # if endpoint.endpoint_name
                # similar_offer_enpoints =
                # endpoint.init_input(
                #     user=self.user,
                #     input_offers=self.input_offers,
                #     params_in=self.params_in,
                #     call_id=self.call_id,
                # )
                pass
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
            input_offers=self.input_offers,
        )

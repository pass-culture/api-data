import copy
from dataclasses import dataclass
import typing as t
import huggy.core.scorer.offer as offer_scorer
from huggy.core.endpoint.ranking_endpoint import RankingEndpoint
from huggy.core.endpoint.retrieval_endpoint import RetrievalEndpoint
from huggy.schemas.offer import Offer
from huggy.schemas.playlist_params import PlaylistParams
from huggy.schemas.user import UserContext
from pydantic import BaseModel

from huggy.core.endpoint.retrieval_endpoint import RetrievalEndpoint
from huggy.core.endpoint.ranking_endpoint import RankingEndpoint
from huggy.schemas.model_selection.model_configuration import (
    DiversificationParams,
    ModelTypeInput,
    WarnModelTypeDefaultInput,
    ForkParamsInput,
    ColdStartModelTypeDefaultInput,
)
import huggy.core.model_selection.endpoint.user_ranking as user_ranking
from enum import Enum


class RankingChoices(Enum):
    DEFAULT = "default"
    DISTANCE = "distance"
    NO_POPULARITY = "no_popularity"


class DiversificationChoices(Enum):
    DEFAULT = "default"
    OFF = "off"
    ON = "on"
    GTL_ID = "gtl_id"
    GTL_LVL3 = "glt_lvl3"
    GTL_LVL4 = "glt_lvl4"


@dataclass
class ModelConfiguration:
    name: str
    description: str
    scorer: offer_scorer.OfferScorer
    retrieval_endpoints: t.List[RetrievalEndpoint]
    ranking_endpoint: RankingEndpoint
    diversification_params: DiversificationParams
    query_order: str = "item_rank"

    def get_diversification_params(
        self, params_in: PlaylistParams
    ) -> DiversificationParams:
        """
        Overwrite default params
        """
        if params_in.is_reco_shuffled is not None:
            self.diversification_params.is_reco_shuffled = params_in.is_reco_shuffled

        if params_in.submixing_feature_dict is not None:
            self.diversification_params.submixing_feature_dict = (
                params_in.submixing_feature_dict
            )

        return self.diversification_params

    async def to_dict(self):
        return {
            "name": self.name,
            "description": self.description,
            "diversification_params": await self.diversification_params.to_dict(),
        }


@dataclass
class ForkOut:
    """"""

    model_configuration: ModelConfiguration
    reco_origin: str
    model_origin: str


@dataclass
class ModelFork:
    warm_start_model: ModelConfiguration
    cold_start_model: ModelConfiguration
    bookings_count: int = 2
    clicks_count: int = 25
    favorites_count: int = None

    def get_user_status(self, user: UserContext, model_origin: str) -> ForkOut:
        """Get model status based on UserContext interactions"""
        if not user.found:
            return ForkOut(
                copy.deepcopy(self.cold_start_model),
                reco_origin="unknown",
                model_origin=model_origin,
            )

        if self.favorites_count is not None:
            if user.favorites_count >= self.favorites_count:
                return ForkOut(
                    copy.deepcopy(self.warm_start_model),
                    reco_origin="algo",
                    model_origin=model_origin,
                )

        if self.bookings_count is not None:
            if user.bookings_count >= self.bookings_count:
                return ForkOut(
                    copy.deepcopy(self.warm_start_model),
                    reco_origin="algo",
                    model_origin=model_origin,
                )

        if self.clicks_count is not None:
            if user.clicks_count >= self.clicks_count:
                return ForkOut(
                    copy.deepcopy(self.warm_start_model),
                    reco_origin="algo",
                    model_origin=model_origin,
                )
        return ForkOut(
            copy.deepcopy(self.cold_start_model),
            reco_origin="cold_start",
            model_origin=model_origin,
        )

    def get_offer_status(self, offer: Offer, model_origin):
        """Get model status based on Offer interactions"""
        if not offer.found:
            return ForkOut(
                copy.deepcopy(self.cold_start_model),
                reco_origin="unknown",
                model_origin=model_origin,
            )
        if self.bookings_count is not None:
            if offer.booking_number >= self.bookings_count:
                return ForkOut(
                    copy.deepcopy(self.warm_start_model),
                    reco_origin="algo",
                    model_origin=model_origin,
                )
        return ForkOut(
            copy.deepcopy(self.cold_start_model),
            reco_origin="cold_start",
            model_origin=model_origin,
        )


class ModelConfigurationInput(BaseModel):
    """Custom modelEndpoint model"""

    name: str
    description: str = """"""
    diversification_params: str = "default"
    warn_model_type: ModelTypeInput = WarnModelTypeDefaultInput()
    cold_start_model_type: ModelTypeInput = ColdStartModelTypeDefaultInput()
    fork_params: ForkParamsInput = ForkParamsInput()

    def get_diversification(self, div_type):
        diversification_on = DiversificationParams(
            is_active=True,
            is_reco_shuffled=False,
            mixing_features="search_group_name",
            order_column="offer_score",
            order_ascending=False,
            submixing_feature_dict=None,
        )
        return {
            DiversificationChoices.DEFAULT: diversification_on,
            DiversificationChoices.OFF: DiversificationParams(
                is_active=False,
                is_reco_shuffled=False,
                mixing_features="search_group_name",
                order_column="offer_score",
                order_ascending=False,
                submixing_feature_dict=None,
            ),
            DiversificationChoices.ON: diversification_on,
            DiversificationChoices.GTL_ID: DiversificationParams(
                is_active=True,
                is_reco_shuffled=True,
                mixing_features="search_group_name",
                order_column="offer_score",
                order_ascending=False,
                submixing_feature_dict={"LIVRES": "gtl_id"},
            ),
            DiversificationChoices.GTL_LVL3: DiversificationParams(
                is_active=True,
                is_reco_shuffled=True,
                mixing_features="search_group_name",
                order_column="offer_score",
                order_ascending=False,
                submixing_feature_dict={"LIVRES": "gtl_l3"},
            ),
            DiversificationChoices.GTL_LVL4: DiversificationParams(
                is_active=True,
                is_reco_shuffled=True,
                mixing_features="search_group_name",
                order_column="offer_score",
                order_ascending=False,
                submixing_feature_dict={"LIVRES": "gtl_l4"},
            ),
        }.get(div_type, diversification_on)

    def get_ranking(self, model_type) -> RankingEndpoint:
        default = user_ranking.user_ranking_endpoint
        return {
            "default": default,
            "distance": user_ranking.user_distance_ranking_endpoint,
            "no_popularity": user_ranking.no_popular_ranking_endpoint,
        }.get(model_type, default)

    def get_retrieval(self, model_type) -> t.List[RetrievalEndpoint]:
        pass

    def generate(self) -> ModelFork:
        cold_start_model = ModelConfiguration(
            name=self.name,
            description=self.description,
            scorer=offer_scorer.OfferScorer,
            retrieval_endpoints=self.get_retrieval(
                self.cold_start_model_type.retrieval
            ),
            ranking_endpoint=self.get_ranking(self.cold_start_model_type.ranking),
            diversification_params=self.get_diversification(
                self.diversification_params
            ),
            query_order=self.cold_start_model_type.query_order,
        )
        warn_model = ModelConfiguration(
            name=self.name,
            description="""""",
            scorer=offer_scorer.OfferScorer,
            retrieval_endpoints=self.get_retrieval(self.warn_model_type.retrieval),
            ranking_endpoint=self.get_ranking(self.warn_model_type.ranking),
            diversification_params=self.get_diversification(
                self.diversification_params
            ),
            query_order=self.warn_model_type.query_order,
        )

        return ModelFork(
            warm_start_model=warn_model,
            cold_start_model=cold_start_model,
            bookings_count=self.fork_params.bookings_count,
            clicks_count=self.fork_params.clicks_count,
            favorites_count=self.fork_params.favorites_count,
        )


class ModelEnpointInput(BaseModel):
    model_name: str = None
    custom_configuration: t.Optional[ModelConfigurationInput] = None

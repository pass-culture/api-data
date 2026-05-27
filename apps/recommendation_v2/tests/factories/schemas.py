import random

from polyfactory.factories.dataclass_factory import DataclassFactory
from polyfactory.factories.pydantic_factory import ModelFactory
from polyfactory.fields import Use

from connectors.vertex_api import RankingPrediction
from connectors.vertex_api import VertexPredictionResult
from core.user_context import UserContext
from schemas.enriched_offer import EnrichedRecommendableOffer
from schemas.playlist_recommendation import CategoryEnum
from schemas.playlist_recommendation import RecommendationResponse
from schemas.playlist_recommendation import SearchGroupNameEnum
from schemas.playlist_recommendation import SubcategoryEnum
from schemas.similar_offer import SimilarOfferResponse
from schemas.vertex_prediction_item import RecommendableItem


class RecommendableItemFactory(ModelFactory[RecommendableItem]):
    __model__ = RecommendableItem

    category = Use(lambda: random.choice(list(CategoryEnum)).value)
    subcategory_id = Use(lambda: random.choice(list(SubcategoryEnum)).value)
    search_group_name = Use(lambda: random.choice(list(SearchGroupNameEnum)).value)


class VertexPredictionResultFactory(ModelFactory[VertexPredictionResult]):
    __model__ = VertexPredictionResult


class RankingPredictionFactory(ModelFactory[RankingPrediction]):
    __model__ = RankingPrediction


class EnrichedRecommendableOfferFactory(DataclassFactory[EnrichedRecommendableOffer]):
    __model__ = EnrichedRecommendableOffer

    category = Use(lambda: random.choice(list(CategoryEnum)).value)
    subcategory_id = Use(lambda: random.choice(list(SubcategoryEnum)).value)
    search_group_name = Use(lambda: random.choice(list(SearchGroupNameEnum)).value)


class UserContextFactory(DataclassFactory[UserContext]):
    __model__ = UserContext


class RecommendationResponseFactory(ModelFactory[RecommendationResponse]):
    __model__ = RecommendationResponse

    from_cache = False


class SimilarOfferResponseFactory(ModelFactory[SimilarOfferResponse]):
    __model__ = SimilarOfferResponse

    from_cache = False

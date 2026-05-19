import random

from polyfactory.factories.pydantic_factory import ModelFactory
from polyfactory.fields import Use

from connectors.vertex_api import RankingPrediction
from connectors.vertex_api import VertexPredictionResult
from schemas.playlist_recommendation import CategoryEnum
from schemas.playlist_recommendation import SearchGroupNameEnum
from schemas.playlist_recommendation import SubcategoryEnum
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

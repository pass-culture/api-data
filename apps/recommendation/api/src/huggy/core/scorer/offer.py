from sqlalchemy.orm import Session
from typing import List
import time
import random

from huggy.core.endpoint.retrieval_endpoint import RetrievalEndpoint
from huggy.core.endpoint.ranking_endpoint import RankingEndpoint

from huggy.schemas.user import User
from huggy.schemas.playlist_params import PlaylistParams
from huggy.schemas.offer import RecommendableOffer
from huggy.schemas.item import RecommendableItem

from huggy.crud.offer import get_nearest_offers, get_non_recommendable_items

from huggy.utils.env_vars import log_duration


class OfferScorer:
    def __init__(
        self,
        user: User,
        params_in: PlaylistParams,
        retrieval_endpoints: List[RetrievalEndpoint],
        ranking_endpoint: RankingEndpoint,
        model_params,
    ):
        self.user = user
        self.model_params = model_params
        self.params_in = params_in
        self.retrieval_endpoints = retrieval_endpoints
        self.ranking_endpoint = ranking_endpoint

    def get_scoring(
        self,
        db: Session,
        call_id,
    ) -> List[RecommendableOffer]:
        start = time.time()

        prediction_items: List[RecommendableItem] = []

        for endpoint in self.retrieval_endpoints:
            prediction_items.extend(endpoint.model_score())
        log_duration(
            f"Retrieval: predicted_items for {self.user.user_id}: predicted_items -> {len(prediction_items)}",
            start,
        )
        start = time.time()
        # nothing to score
        if len(prediction_items) == 0:
            return []

        # Transform items in offers
        recommendable_offers = self.get_recommendable_offers(db, prediction_items)

        # nothing to score
        if len(recommendable_offers) == 0:
            return []

        recommendable_offers = self.ranking_endpoint.model_score(
            recommendable_offers=recommendable_offers
        )
        log_duration(
            f"Ranking: get_recommendable_offers for {self.user.user_id}: offers -> {len(recommendable_offers)}",
            start,
        )

        return recommendable_offers

    def get_recommendable_offers(
        self,
        db: Session,
        recommendable_items: List[RecommendableItem],
    ) -> List[RecommendableOffer]:
        start = time.time()
        non_recommendable_items = get_non_recommendable_items(db, self.user)

        recommendable_items_ids = {
            item.item_id: item.item_rank
            for item in recommendable_items
            if item.item_id not in non_recommendable_items
        }
        recommendable_offers_db = get_nearest_offers(
            db, self.user, recommendable_items_ids
        )
        log_duration(
            f"GLOBAL. get_nearest_offers {str(self.user.user_id)} offers : {len(recommendable_offers_db)}",
            start,
        )
        size = len(recommendable_offers_db)
        recommendable_offers = []
        for i, ro in enumerate(recommendable_offers_db):
            recommendable_offers.append(
                RecommendableOffer(
                    offer_id=ro.offer_id,
                    item_id=ro.item_id,
                    venue_id=ro.venue_id,
                    user_distance=ro.user_distance,
                    booking_number=ro.booking_number,
                    stock_price=ro.stock_price,
                    offer_creation_date=ro.offer_creation_date,
                    stock_beginning_date=ro.stock_beginning_date,
                    category=ro.category,
                    subcategory_id=ro.subcategory_id,
                    search_group_name=ro.search_group_name,
                    venue_latitude=ro.venue_latitude,
                    venue_longitude=ro.venue_longitude,
                    is_geolocated=ro.is_geolocated,
                    item_rank=recommendable_items_ids[ro.item_id],
                    offer_score=size - i,
                )
            )

        return recommendable_offers

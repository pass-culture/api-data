from typing import List
from huggy.schemas.offer import Offer


def limit_offers(offer_limit: int = 20, list_offers: List[Offer] = None):
    return list_offers[:offer_limit]

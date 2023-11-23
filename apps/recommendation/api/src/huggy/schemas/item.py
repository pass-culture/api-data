from dataclasses import dataclass


@dataclass
class RecommendableItem:
    item_id: str
    item_rank: int
    item_origin: str

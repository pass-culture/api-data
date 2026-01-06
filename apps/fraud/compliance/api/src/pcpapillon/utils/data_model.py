from enum import Enum
from typing import Any, List

from pydantic import BaseModel, Field


class ComplianceInput(BaseModel):
    offer_id: str | None = ""
    offer_name: str | None = ""
    offer_description: str | None = ""
    offer_subcategory_id: str | None = ""
    rayon: str | None = ""
    macro_rayon: str | None = ""
    stock_price: float | None = 0
    image_url: str | None = ""
    offer_type_label: str | None = ""
    offer_sub_type_label: str | None = ""
    author: str | None = ""
    performer: str | None = ""


class ComplianceOutput(BaseModel):
    offer_id: str
    probability_validated: int
    validation_main_features: list[str]
    probability_rejected: int
    rejection_main_features: list[str]


class ModelParams(BaseModel):
    name: str = "default"
    type: str = "default"


class SearchEditoColumn(str, Enum):
    offer_category_id = "offer_category_id"
    offer_subcategory_id = "offer_subcategory_id"
    venue_department_code = "venue_department_code"
    last_stock_price = "last_stock_price"
    offer_creation_date = "offer_creation_date"
    stock_beginning_date = "stock_beginning_date"


class SearchEditoFilter(BaseModel):
    column: SearchEditoColumn = Field(..., description="Column to filter on")
    operator: str = Field(
        ..., description="Operator for the filter (e.g., '=', '>', '<', 'in')"
    )
    value: Any = Field(..., description="Value to compare the column against")


class SearchEditoInput(BaseModel):
    query: str | None = Field("", description="Search query string")
    filters: List[SearchEditoFilter] | None = Field(
        None, description="List of filters to apply to the search"
    )


class OfferEditoSelection(BaseModel):
    offer_id: str = Field(..., description="Unique identifier of the offer")
    pertinence: str = Field(..., description="Pertinence score or label for the offer")


class SearchEditoOutput(BaseModel):
    results: list[OfferEditoSelection]

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class SearchEditoColumn(str, Enum):
    offer_category_id = "offer_category_id"
    offer_subcategory_id = "offer_subcategory_id"
    venue_department_code = "venue_department_code"
    last_stock_price = "last_stock_price"
    offer_creation_date = "offer_creation_date"
    stock_beginning_date = "stock_beginning_date"


class SearchEditoFilter(BaseModel):
    column: SearchEditoColumn = Field(..., description="Column to filter on")
    operator: Literal["=", ">", "<", "in", "not in", "=<", ">="] = Field(
        ...,
        description="Operator for the filter (e.g., '=', '>', '<', 'in', 'not in', '=<', '>=')",
    )
    value: Any = Field(..., description="Value to compare the column against")


class SearchEditoInput(BaseModel):
    query: str | None = Field("", description="Search query string")
    filters: list[SearchEditoFilter] | None = Field(
        None, description="List of filters to apply to the search"
    )


class OfferEditoSelection(BaseModel):
    offer_id: str = Field(..., description="Unique identifier of the offer")
    pertinence: str = Field(..., description="Pertinence score or label for the offer")


class SearchEditoOutput(BaseModel):
    results: list[OfferEditoSelection]

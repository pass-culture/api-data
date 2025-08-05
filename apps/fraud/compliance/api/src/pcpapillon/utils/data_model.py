# from __future__ import annotations

from pydantic import BaseModel


class User(BaseModel):
    username: str
    disabled: bool | None = None


class UserInDB(User):
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: str | None = None


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

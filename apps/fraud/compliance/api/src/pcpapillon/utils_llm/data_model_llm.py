# from __future__ import annotations
from typing import Union

from pydantic import BaseModel


class User(BaseModel):
    username: str
    disabled: Union[bool, None] = None


class UserInDB(User):
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Union[str, None] = None


class LLMComplianceInput(BaseModel):
    offer_id: Union[str, None] = ""
    offer_name: Union[str, None] = ""
    offer_description: Union[str, None] = ""
    offer_subcategory_id: Union[str, None] = ""
    last_stock_price: Union[float, None] = 0


class LLMComplianceOutput(BaseModel):
    offer_id: str
    réponse_LLM: str
    explication_classification: str

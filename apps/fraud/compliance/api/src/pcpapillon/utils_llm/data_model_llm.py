from pydantic import BaseModel
from enum import Enum


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


class LLMComplianceInput(BaseModel):
    offer_id: str | None = ""
    offer_name: str | None = ""
    offer_description: str | None = ""
    offer_subcategory_id: str | None = ""
    last_stock_price: float | None = 0


# class LLMComplianceOutput(BaseModel):
#     offer_id: str
#     réponse_LLM: str
#     explication_classification: str

class ComplianceValidationStatusPrediction(Enum):
    APPROVED = "approved"
    REJECTED = "rejected"

class ComplianceValidationStatusPredictionOutput(BaseModel):
    validation_status_prediction: ComplianceValidationStatusPrediction | None
    validation_status_prediction_reason: str | None

from enum import Enum

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


class LLMComplianceInput(BaseModel):
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


class ComplianceOutput(BaseModel):
    offer_id: str
    probability_validated: int
    validation_main_features: list[str]
    probability_rejected: int
    rejection_main_features: list[str]
    validation_status_prediction: ComplianceValidationStatusPrediction | None = None
    validation_status_prediction_reason: str | None = None

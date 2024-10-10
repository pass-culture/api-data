from enum import Enum


def fake_model(a: int, b: str) -> int:
    return a + b


class ModelName(Enum):
    """
    Enum class for model names
    """

    OFFER_CATEGORISATION = "offer_categorization"
    COMPLIANCE = "compliance_default"

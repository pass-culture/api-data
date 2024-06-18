from enum import Enum

from pcpapillon.utils.env_vars import (
    COMPLIANCE_MODEL_PATH,
    OFFER_CATEGORISATION_MODEL_PATH,
)


class ModelName(Enum):
    """
    Enum class for model names
    """

    OFFER_CATEGORISATION = "offer_categorisation"
    COMPLIANCE = "compliance"


class ModelType(Enum):
    """
    Enum class for model types
    """

    LOCAL = "local"
    DEFAULT = "default"
    PREPROCESSING = "custom_sentence_transformer"


class ConfigName(Enum):
    """
    Enum class for config names
    """

    API = "API"
    MODEL = "model"


class APIType(Enum):
    """
    Enum class for API types
    """

    DEFAULT = "default"


MODEL_PATHS = {
    ModelName.COMPLIANCE: COMPLIANCE_MODEL_PATH,
    ModelName.OFFER_CATEGORISATION: OFFER_CATEGORISATION_MODEL_PATH,
}

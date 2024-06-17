from enum import Enum


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


MLFLOW_TRACKING_TOKEN_ENV_VAR = "MLFLOW_TRACKING_TOKEN"
MODEL_PATHS = {
    ModelName.COMPLIANCE: "pcpapillon/local_model/model.cb",
    ModelName.OFFER_CATEGORISATION: "pcpapillon/local_model/offer_categorisation_model.cb",
}

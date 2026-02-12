import contextvars
from enum import Enum

from pcpapillon.utils.env_vars import ENV_SHORT_NAME
from pcpapillon.utils.secrets import access_secret


class ModelName(Enum):
    """
    Enum class for model names
    """

    OFFER_CATEGORISATION = "offer_categorization"
    COMPLIANCE = "compliance_default"


# logger
cloud_trace_context = contextvars.ContextVar("cloud_trace_context", default="")
call_id_trace_context = contextvars.ContextVar("call_id_context", default="")
http_request_context = contextvars.ContextVar("http_request_context", default={})


# Constants
GCP_PROJECT = (
    "passculture-data-prod" if ENV_SHORT_NAME == "prod" else "passculture-data-ehp"
)
SA_ACCOUNT = f"algo-training-{ENV_SHORT_NAME}"


# MLFlow
MLFLOW_CLIENT_ID = access_secret(GCP_PROJECT, "mlflow_client_id")
MLFLOW_URL = (
    "https://mlflow.passculture.team/"
    if ENV_SHORT_NAME == "prod"
    else "https://mlflow.staging.passculture.team/"
)


# Search edito
LLM_ALLOWED_SUBCATEGORY_WITH_MAPPING = {
    "ACHAT_INSTRUMENT": "instruments",
    "LOCATION_INSTRUMENT": "instruments",
    "PARTITION": "instruments",
    "ABO_PRATIQUE_ART": "pratiques_artistiques",
    "ATELIER_PRATIQUE_ART": "pratiques_artistiques",
    "LIVESTREAM_PRATIQUE_ARTISTIQUE": "pratiques_artistiques",
    "SEANCE_ESSAI_PRATIQUE_ART": "pratiques_artistiques",
    "PRATIQUE_ART_VENTE_DISTANCE": "pratiques_artistiques",
    "CONCERT": "spectacle_vivant",
    "SPECTACLE_REPRESENTATION": "spectacle_vivant",
    "FESTIVAL_MUSIQUE": "spectacle_vivant",
    "EVENEMENT_MUSIQUE": "spectacle_vivant",
    "ABO_CONCERT": "spectacle_vivant",
    "FESTIVAL_SPECTACLE": "spectacle_vivant",
    "SPECTACLE_VENTE_DISTANCE": "spectacle_vivant",
}
PRICE_CHECK_CATEGORIES = ["instruments"]

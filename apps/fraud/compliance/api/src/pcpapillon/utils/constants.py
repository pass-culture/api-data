import contextvars

from pcpapillon.utils.env_vars import ENV_SHORT_NAME


cloud_trace_context = contextvars.ContextVar("cloud_trace_context", default="")
call_id_trace_context = contextvars.ContextVar("call_id_context", default="")
http_request_context = contextvars.ContextVar("http_request_context", default={})

GCP_PROJECT = (
    "passculture-data-prod" if ENV_SHORT_NAME == "prod" else "passculture-data-ehp"
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
    "LIVRE_PAPIER": "livres",
    "LIVRE_NUMERIQUE": "livres",
}
PRICE_CHECK_CATEGORIES = ["instruments"]
BOOK_CHECK_CATEGORIES = ["livres"]

import traceback

from fastapi import APIRouter, Depends
from fastapi_versioning import version

from pcpapillon.core.llm_compliance_model import LLMComplianceModel
from pcpapillon.utils.constants import (
    BOOK_CHECK_CATEGORIES,
    LLM_ALLOWED_SUBCATEGORY_WITH_MAPPING,
    PRICE_CHECK_CATEGORIES,
)
from pcpapillon.utils.logging.trace import custom_logger, get_call_id, setup_trace
from pcpapillon.utils_llm.data_model_llm import (
    ComplianceOutput,
    LLMComplianceInput,
)

compliance_router = APIRouter(tags=["compliance"])


@compliance_router.post(
    "/model/compliance/scoring",
    response_model=ComplianceOutput,
    dependencies=[Depends(get_call_id), Depends(setup_trace)],
)
@version(1, 0)
def model_compliance_scoring(scoring_input: LLMComplianceInput) -> ComplianceOutput:
    log_extra_data = {
        "model_version": "default_model",
        "offer_id": scoring_input.offer_id,
        "scoring_input": scoring_input.model_dump(),
    }
    # Default values bypass LLM scoring when the subcategory is not in the allowed list.
    predictions: dict = {
        "offer_id": scoring_input.offer_id,
        "probability_validated": 50,
        "validation_main_features": ["NA"],
        "probability_rejected": 50,
        "rejection_main_features": ["NA"],
    }
    if scoring_input.offer_subcategory_id in LLM_ALLOWED_SUBCATEGORY_WITH_MAPPING:
        try:
            llm_model = LLMComplianceModel()
            rule_apply = LLM_ALLOWED_SUBCATEGORY_WITH_MAPPING[scoring_input.offer_subcategory_id]
            if rule_apply in PRICE_CHECK_CATEGORIES or rule_apply in BOOK_CHECK_CATEGORIES:
                llm_model.config["validation"]["mode"] = "sequential_pipeline"
            predictions_llm = llm_model.predict(data=scoring_input)
            predictions.update(predictions_llm.model_dump(mode="json"))
        except Exception as err:
            custom_logger.error(
                "Error during LLM compliance prediction",
                extra={
                    "error": str(err),
                    "trace": traceback.format_exc(),
                    **log_extra_data,
                },
            )
    custom_logger.info(predictions, extra=log_extra_data)
    return predictions

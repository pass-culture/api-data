import traceback

from fastapi import APIRouter, Depends
from fastapi_versioning import version
from pcpapillon.core.compliance_model import (
    ComplianceModel,
)
from pcpapillon.core.llm_compliance_model import LLMComplianceModel
from pcpapillon.utils.env_vars import LLM_ALLOWED_SUBCATEGORY_WITH_MAPPING
from pcpapillon.utils.logging.trace import custom_logger, get_call_id, setup_trace
from pcpapillon.utils.scheduler import init_scheduler
from pcpapillon.utils_llm.data_model_llm import (
    ComplianceOutput,
    LLMComplianceInput,
)

compliance_router = APIRouter(tags=["compliance"])


# Init model and scheduler
compliance_model = ComplianceModel()
compliance_scheduler = init_scheduler(
    compliance_model.reload_model_if_newer_is_available, time_interval=600
)


@compliance_router.post(
    "/model/compliance/scoring",
    response_model=ComplianceOutput,
    dependencies=[Depends(get_call_id), Depends(setup_trace)],
)
@version(1, 0)
def model_compliance_scoring(scoring_input: LLMComplianceInput):
    log_extra_data = {
        "model_version": "default_model",
        "offer_id": scoring_input.dict()["offer_id"],
        "scoring_input": scoring_input.dict(),
    }
    input_data = scoring_input.dict()
    predictions = compliance_model.predict(data=scoring_input)
    predictions = predictions.dict()

    llm_model = LLMComplianceModel()
    if (
        input_data["offer_subcategory_id"]
        in LLM_ALLOWED_SUBCATEGORY_WITH_MAPPING.keys()
    ):
        try:
            rule_apply = LLM_ALLOWED_SUBCATEGORY_WITH_MAPPING.get(
                input_data["offer_subcategory_id"]
            )
            # Here only instruments need a price check
            if rule_apply == "instruments":
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

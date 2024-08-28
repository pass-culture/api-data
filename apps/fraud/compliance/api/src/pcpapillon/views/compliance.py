from fastapi import APIRouter, Depends
from fastapi_versioning import version
from main import custom_logger, setup_trace
from pcpapillon.core.compliance_model import (
    ComplianceModel,
)
from pcpapillon.utils.data_model import (
    ComplianceInput,
    ComplianceOutput,
)
from pcpapillon.utils.scheduler import init_scheduler

compliance_router = APIRouter(tags=["compliance"])


# Init model and scheduler
compliance_model = ComplianceModel()
compliance_scheduler = init_scheduler(
    compliance_model.reload_model_if_newer_is_available, time_interval=600
)


@compliance_router.post(
    "/model/compliance/scoring",
    response_model=ComplianceOutput,
    dependencies=[Depends(setup_trace)],
)
@version(1, 0)
def model_compliance_scoring(scoring_input: ComplianceInput):
    log_extra_data = {
        "model_version": "default_model",
        "offer_id": scoring_input.dict()["offer_id"],
        "scoring_input": scoring_input.dict(),
    }

    predictions = compliance_model.predict(data=scoring_input.dict())

    validation_response_dict = {
        "offer_id": scoring_input.dict()["offer_id"],
        "probability_validated": predictions.probability_validated,
        "validation_main_features": predictions.validation_main_features,
        "probability_rejected": predictions.probability_rejected,
        "rejection_main_features": predictions.rejection_main_features,
    }
    custom_logger.info(validation_response_dict, extra=log_extra_data)
    return validation_response_dict

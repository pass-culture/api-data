from fastapi import APIRouter, Depends
from fastapi_versioning import version
from main import custom_logger, setup_trace
from pcpapillon.core.compliance.compliance_model import (
    ComplianceModel,
)
from pcpapillon.core.compliance.loaders import load_config
from pcpapillon.utils.data_model import (
    ComplianceInput,
    ComplianceOutput,
    ModelParams,
    User,
)
from pcpapillon.utils.security import (
    get_current_active_user,
)
from typing_extensions import Annotated

compliance_router = APIRouter(tags=["compliance"])


# Init model and configs
api_config, model_config = load_config()
compliance_model = ComplianceModel(api_config=api_config, model_config=model_config)


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

    (
        proba_validation,
        proba_rejection,
        top_validation,
        top_rejection,
    ) = compliance_model.predict(data=scoring_input.dict())

    validation_response_dict = {
        "offer_id": scoring_input.dict()["offer_id"],
        "probability_validated": proba_validation,
        "validation_main_features": top_validation,
        "probability_rejected": proba_rejection,
        "rejection_main_features": top_rejection,
    }
    custom_logger.info(validation_response_dict, extra=log_extra_data)
    return validation_response_dict


@compliance_router.post("/model/compliance/load", dependencies=[Depends(setup_trace)])
@version(1, 0)
def model_compliance_load(
    model_params: ModelParams,
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    log_extra_data = {"model_params": model_params.dict()}
    custom_logger.info("Loading new model", extra=log_extra_data)

    compliance_model.reload_classification_model(model_params=model_params)

    custom_logger.info("Validation model updated", extra=log_extra_data)
    return model_params

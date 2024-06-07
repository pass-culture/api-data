from fastapi import APIRouter, Depends
from fastapi_versioning import version
from main import custom_logger, setup_trace
from pcpapillon.core.predict import get_prediction_and_main_contribution
from pcpapillon.core.preprocess import preprocess
from pcpapillon.utils.compliance import load_config, load_models
from pcpapillon.utils.config_handler import ConfigHandler
from pcpapillon.utils.data_model import (
    ComplianceInput,
    ComplianceOutput,
    ModelParams,
    User,
)
from pcpapillon.utils.model_handler import ModelHandler
from pcpapillon.utils.security import (
    get_current_active_user,
)
from typing_extensions import Annotated

compliance_router = APIRouter(tags=["compliance"])


# Init model and configs
api_config, model_config = load_config()
model_loaded, prepoc_models = load_models(model_config=model_config)


@compliance_router.post(
    "/model/compliance/scoring",
    response_model=ComplianceOutput,
    dependencies=[Depends(setup_trace)],
)
@version(1, 0)
def model_compliance_scoring(item: ComplianceInput):
    log_extra_data = {
        "model_version": "default_model",
        "offer_id": item.dict()["offer_id"],
        "scoring_input": item.dict(),
    }
    custom_logger.info(prepoc_models)
    pool, data_w_emb = preprocess(api_config, model_config, item.dict(), prepoc_models)
    (
        proba_validation,
        proba_rejection,
        top_validation,
        top_rejection,
    ) = get_prediction_and_main_contribution(model_loaded, data_w_emb, pool)

    validation_response_dict = {
        "offer_id": item.dict()["offer_id"],
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
    # Update model and config in all workers by using globla variables
    global model_config
    global model_loaded

    log_extra_data = {"model_params": model_params.dict()}
    custom_logger.info("Loading new model", extra=log_extra_data)

    config_handler = ConfigHandler()
    model_handler = ModelHandler(model_config)
    model_loaded = model_handler.get_model_by_name(model_params.name, model_params.type)
    model_config = config_handler.get_config_by_name_and_type(
        "model", model_params.type
    )

    custom_logger.info("Validation model updated", extra=log_extra_data)
    return model_params

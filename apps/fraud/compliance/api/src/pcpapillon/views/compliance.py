from fastapi import APIRouter, Depends
from fastapi_versioning import version
from main import custom_logger, setup_trace
from pcpapillon.core.predict import get_prediction_and_main_contribution
from pcpapillon.core.preprocess import preprocess
from pcpapillon.utils.config_handler import ConfigHandler
from pcpapillon.utils.data_model import (
    ComplianceOutput,
    Item,
    ModelParams,
    User,
)
from pcpapillon.utils.env_vars import (
    isAPI_LOCAL,
)
from pcpapillon.utils.model_handler import ModelHandler
from pcpapillon.utils.security import (
    get_current_active_user,
)
from typing_extensions import Annotated

compliance_router = APIRouter(tags=["compliance"])

config_handler = ConfigHandler()
api_config = config_handler.get_config_by_name_and_type("API", "default")
model_config = config_handler.get_config_by_name_and_type("model", "default")

model_handler = ModelHandler(model_config)
custom_logger.info("load_compliance_model..")
model_loaded = model_handler.get_model_by_name(
    name="compliance", type="local" if isAPI_LOCAL else "default"
)
custom_logger.info("load_preproc_model..")
prepoc_models = {}
for feature_type in model_config.pre_trained_model_for_embedding_extraction.keys():
    prepoc_models[feature_type] = model_handler.get_model_by_name(feature_type)


@compliance_router.post(
    "/model/compliance/scoring",
    response_model=ComplianceOutput,
    dependencies=[Depends(setup_trace)],
)
@version(1, 0)
def model_compliance_scoring(item: Item):
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
    log_extra_data = {"model_params": model_params.dict()}
    custom_logger.info("Loading new model", extra=log_extra_data)
    global model_loaded
    model_loaded = model_handler.get_model_by_name(model_params.name, model_params.type)
    global model_config
    model_config = config_handler.get_config_by_name_and_type(
        "model", model_params.type
    )
    custom_logger.info("Validation model updated", extra=log_extra_data)
    return model_params

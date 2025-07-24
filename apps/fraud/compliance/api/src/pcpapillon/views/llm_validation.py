from typing import Union

from fastapi import APIRouter, Depends
from fastapi_versioning import version
from openai import OpenAI
from pcpapillon.utils.logging.trace import custom_logger, get_call_id, setup_trace
from pydantic import BaseModel
from utils.env_vars import OPENAI_API_KEY

llm_router = APIRouter(tags=["llm-validation"])


class LLMValidationInput(BaseModel):
    offer_id: Union[str, None] = ""
    offer_name: Union[str, None] = ""
    # offer_description: Union[str, None] = ""
    # offer_subcategory_id: Union[str, None] = ""
    # rayon: Union[str, None] = ""
    # macro_rayon: Union[str, None] = ""
    # stock_price: Union[float, None] = 0
    # image_url: Union[str, None] = ""
    # offer_type_label: Union[str, None] = ""
    # offer_sub_type_label: Union[str, None] = ""
    # author: Union[str, None] = ""
    # performer: Union[str, None] = ""


class LLMValidationOutput(BaseModel):
    offer_id: str
    validation_status: str
    explaination: str
    # validation_main_features: list[str]
    # probability_rejected: int
    # rejection_main_features: list[str]


# compliance_model = ComplianceModel()
# compliance_scheduler = init_scheduler(
#     compliance_model.reload_model_if_newer_is_available, time_interval=600
# )


def mock_llm_analysis(data: dict):
    """
    Mock function to simulate LLM analysis
    """

    # It's best practice to load your API key from an environment variable
    # For simplicity in this example, you could also replace os.environ.get("OPENAI_API_KEY") with "YOUR_API_KEY"
    client = OpenAI(api_key=OPENAI_API_KEY)

    response = client.chat.completions.create(
        model="gpt-4o",  # You can choose other models like "gpt-3.5-turbo"
        messages=[{"role": "user", "content": "Tell me a short, funny joke."}],
    )
    return {
        "offer_id": data.dict()["offer_id"],
        "validation_status": "validated",  # This could be "validated" or "rejected"
        "explaination": response.choices[0].message.content,
    }


@llm_router.post(
    "/model/llm-validation/scoring",
    response_model=LLMValidationOutput,
    dependencies=[Depends(get_call_id), Depends(setup_trace)],
)
@version(1, 0)
def model_compliance_scoring(llm_validation_input: LLMValidationInput):
    log_extra_data = {
        "model_version": "default_model",
        "offer_id": llm_validation_input.dict()["offer_id"],
        "scoring_input": llm_validation_input.dict(),
    }

    # predictions = compliance_model.predict(data=llm_validation_input)
    predictions = mock_llm_analysis(llm_validation_input)

    custom_logger.info(predictions, extra=log_extra_data)
    return predictions

import os

import yaml
from loguru import logger

from pcpapillon.utils_llm.data_model_llm import (
    ComplianceValidationStatusPredictionOutput,
    LLMComplianceInput,
)
from pcpapillon.utils_llm.pipeline import run_validation_pipeline

script_dir = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(
    script_dir, "..", "utils_llm", "configs", "global_llm_calls_config.yaml"
)


class LLMComplianceModel:
    def __init__(self):
        self.config = self._load_config()

    def _load_config(self) -> dict:
        with open(config_path) as f:
            return yaml.safe_load(f)

    def predict(
        self, data: LLMComplianceInput
    ) -> ComplianceValidationStatusPredictionOutput:
        offer = data.model_dump()
        for col in self.config["columns"].get("drop", []):
            offer.pop(col, None)

        result = run_validation_pipeline(self.config, offer)
        if isinstance(result.get("validation_status_prediction"), str):
            result["validation_status_prediction"] = result[
                "validation_status_prediction"
            ].lower()
        logger.info(f"Validation result for offer {offer.get('offer_id')}: {result}")
        return ComplianceValidationStatusPredictionOutput.model_validate(result)

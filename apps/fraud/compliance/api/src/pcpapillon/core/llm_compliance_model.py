import os

import openai
import pandas as pd
import vertexai
import yaml
from dotenv import load_dotenv
from loguru import logger
from pcpapillon.utils.env_vars import OPENAI_API_KEY
from pcpapillon.utils_llm.data_model_llm import (
    ComplianceValidationStatusPredictionOutput,
    LLMComplianceInput,
)
from pcpapillon.utils_llm.run_llm_calls import run_validation_pipeline

script_dir = os.path.dirname(os.path.abspath(__file__))
ConfigPath = os.path.join(
    script_dir, "..", "utils_llm", "configs", "global_llm_calls_config.yaml"
)


class LLMComplianceModel:
    def __init__(self):
        self.config = self._load_config()

    def _load_config(self) -> dict:
        """Load configuration from YAML file."""
        with open(ConfigPath) as f:
            return yaml.safe_load(f)

    def _setup_environment(self):
        """Setup API keys and environment variables."""
        load_dotenv()

        # OpenAI setup
        openai.api_key = os.getenv("OPENAI_API_KEY")

        # Vertex AI setup (if needed)
        project_id = os.getenv("PROJECT_ID")
        location = os.getenv("LOCATION")
        if project_id and location:
            vertexai.init(project=project_id, location=location)
            logger.info("Vertex AI initialized")

    def predict(
        self, data: LLMComplianceInput
    ) -> ComplianceValidationStatusPredictionOutput:
        """
        Predicts the class labels for the given data using the trained classifier model.

        Args:
            data (ComplianceInput): Input data to be predicted.

        Returns:
            ComplianceOutput: An object containing the predicted class labels
                and the main contributions.
        """
        self._setup_environment()
        data = pd.DataFrame.from_dict([data.model_dump()])

        # Drop des colonnes inutiles
        columns_to_drop = self.config["columns"].get("drop", [])
        data = data.drop(columns=columns_to_drop, errors="ignore")

        results_df = run_validation_pipeline(self.config, data)
        results_dict = results_df.to_dict(orient="records")[0]

        # Gestion des deux modes de validation
        validation_mode = self.config["validation"].get("mode", "llm_only")

        if validation_mode == "llm_only":
            # Mode LLM seul : utiliser les colonnes de base
            response = results_dict.get("reponse_LLM")
            explanation = results_dict.get("explication_classification")
        else:
            # Mode sequential : utiliser les colonnes finales
            response = results_dict.get("reponse_LLM_finale")
            explanation = results_dict.get("explication_finale")

        normalized_output = {
            # "offer_id": results_dict.get("offer_id"),
            "validation_status_prediction": response,
            "validation_status_prediction_reason": explanation,
        }

        return ComplianceValidationStatusPredictionOutput.model_validate(
            normalized_output
        )

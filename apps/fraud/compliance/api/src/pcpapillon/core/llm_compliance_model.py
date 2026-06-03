import os

import pandas as pd
import yaml
from loguru import logger

from pcpapillon.utils_llm.data_model_llm import (
    ComplianceValidationStatusPredictionOutput,
    LLMComplianceInput,
)
from pcpapillon.utils_llm.run_llm_calls import run_validation_pipeline

script_dir = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(
    script_dir, "..", "utils_llm", "configs", "global_llm_calls_config.yaml"
)


class LLMComplianceModel:
    def __init__(self):
        self.config = self._load_config()

    def _load_config(self) -> dict:
        """Load configuration from YAML file."""
        with open(config_path) as f:
            return yaml.safe_load(f)

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
        data = pd.DataFrame.from_dict([data.model_dump()])

        # Drop des colonnes inutiles
        columns_to_drop = self.config["columns"].get("drop", [])
        data = data.drop(columns=columns_to_drop, errors="ignore")

        results_df = run_validation_pipeline(self.config, data)
        results_dict = results_df.to_dict(orient="records")[0]

        # Log the results for debugging
        logger.debug(f"Results DataFrame columns: {results_df.columns.tolist()}")
        logger.debug(f"Results dict keys: {list(results_dict.keys())}")
        logger.debug(f"Results dict values: {results_dict}")

        # Gestion des deux modes de validation
        validation_mode = self.config["validation"].get("mode", "llm_only")

        if validation_mode == "llm_only":
            # Mode LLM seul : utiliser les colonnes de base
            response = results_dict.get("reponse_LLM")
            explanation = results_dict.get("explication_classification")
            logger.info(
                f"LLM only mode - response: {response}, explanation: {explanation}"
            )
        else:
            # Mode sequential : utiliser les colonnes finales
            response = results_dict.get("reponse_LLM_finale")
            explanation = results_dict.get("explication_finale")
            logger.info(
                f"Sequential mode - response: {response}, explanation: {explanation}"
            )

        normalized_output = {
            "validation_status_prediction": response,
            "validation_status_prediction_reason": explanation,
        }

        logger.info(f"Normalized output: {normalized_output}")

        return ComplianceValidationStatusPredictionOutput.model_validate(
            normalized_output
        )

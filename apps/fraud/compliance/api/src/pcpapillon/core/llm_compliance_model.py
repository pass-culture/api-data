import os

import openai
import pandas as pd
import vertexai
import yaml
from dotenv import load_dotenv
from loguru import logger
from pcpapillon.utils_llm.data_model_llm import LLMComplianceInput, LLMComplianceOutput
from pcpapillon.utils_llm.run_llm_calls import run_validation_pipeline

ConfigPath = """../utils_llm/configs/global_llm_calls_config.yaml"""


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

    def load_data(self, config: dict) -> pd.DataFrame:
        """Load and prepare data based on configuration."""
        data_format = config["input"].get("format", "parquet")
        data_path = config["input"]["data_path"]

        logger.info(f"Loading data from {data_path} in {data_format} format")

    def filter_offers_for_web_search(
        self, offers: pd.DataFrame, llm_results: pd.DataFrame, config: dict
    ) -> pd.DataFrame:
        """
        Filter offers that should undergo web search based on LLM results and config.

        Args:
            offers: Original offers DataFrame
            llm_results: Results from LLM validation
            config: Configuration dictionary

        Returns:
            Filtered DataFrame of offers for web search
        """
        web_search_conditions = config["validation"].get("web_search_conditions", {})

        if not web_search_conditions:
            logger.info("No web search conditions specified, using all offers")
            return offers

        # Example filtering logic - customize based on your needs
        filtered_offers = offers.copy()

        # Filter based on LLM results if conditions are specified
        if "llm_result_condition" in web_search_conditions:
            condition = web_search_conditions["llm_result_condition"]
            # Add your filtering logic here based on LLM results
            logger.info(f"Applying LLM result condition: {condition}")

            if not llm_results.empty and condition == "needs_verification":
                # Assuming both DataFrames have the same index
                # Get indices where llm_needs_verification is True
                verification_needed_indices = filtered_offers[
                    filtered_offers["llm_needs_verification"]
                ].index

                # Filter offers using these indices
                filtered_offers = offers.loc[verification_needed_indices]

                logger.info(
                    f"Kept {len(filtered_offers)} offers that need verification"
                )
                return filtered_offers
            else:
                logger.warning(
                    "No valid condition or empty LLM results, keeping all offers"
                )

        logger.info(
            f"Filtered {len(offers)} offers to {len(filtered_offers)} for web search"
        )
        return filtered_offers

    def enrich_offers_with_llm_results(
        self, offers: pd.DataFrame, llm_results: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Enrich original offers with LLM validation results for the next validation step.

        Args:
            offers: Original offers DataFrame
            llm_results: Results from first LLM validation

        Returns:
            Enriched offers DataFrame with LLM results as additional context
        """
        # Merge LLM results back into offers
        enriched_offers = offers.merge(
            llm_results, on="offer_id", how="left", suffixes=("", "_llm_result")
        )

        logger.info(f"Enriched {len(offers)} offers with LLM validation results")
        logger.info(
            f"New columns added: {
                [col for col in enriched_offers.columns if col.endswith('_llm_result')]
            }"
        )

        return enriched_offers

    def predict(self, data: LLMComplianceInput) -> LLMComplianceOutput:
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
        # récupérer le fichier de règles selon la sous-catégorie
        # data[offer_subcategory_id]
        results_df = run_validation_pipeline(self.config, data)
        results_dict = results_df.to_dict(orient="records")[0]
        return LLMComplianceOutput.model_validate(results_dict)

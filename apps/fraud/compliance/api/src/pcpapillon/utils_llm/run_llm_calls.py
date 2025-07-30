"""
Unified validation orchestrator supporting both LLM and web search validation.
"""

import os
from pathlib import Path

import openai
import pandas as pd
import vertexai
import yaml

# Import both validation modules
from core import get_llm_validation
from core_web_search import get_web_check
from dotenv import load_dotenv
from loguru import logger


# def load_config(config_path: str | None = None) -> dict:
#     """Load configuration from YAML file."""
#     default_config_path = (
#         Path(__file__).parent / "utils" / "configs" / "global_llm_calls_config.yaml"
#     )
#     config_path = Path(config_path) if config_path else default_config_path

#     if not config_path.exists():
#         raise FileNotFoundError(f"Configuration file not found: {config_path}")

#     with open(config_path) as f:
#         return yaml.safe_load(f)


# def setup_environment():
#     """Setup API keys and environment variables."""
#     load_dotenv()

#     # OpenAI setup
#     openai.api_key = os.getenv("OPENAI_API_KEY")

#     # Vertex AI setup (if needed)
#     project_id = os.getenv("PROJECT_ID")
#     location = os.getenv("LOCATION")
#     if project_id and location:
#         vertexai.init(project=project_id, location=location)
#         logger.info("Vertex AI initialized")


# def load_data(config: dict) -> pd.DataFrame:
#     """Load and prepare data based on configuration."""
#     data_format = config["input"].get("format", "parquet")
#     data_path = config["input"]["data_path"]

#     logger.info(f"Loading data from {data_path} in {data_format} format")

#     # Load data
#     if data_format == "parquet":
#         offers = pd.read_parquet(data_path, engine="pyarrow")
#     elif data_format == "csv":
#         offers = pd.read_csv(data_path)
#     else:
#         raise ValueError(f"Unsupported data format: {data_format}")

#     # Apply column filtering
#     if config["columns"].get("drop"):
#         drop_columns = config["columns"]["drop"]
#         if isinstance(drop_columns, str):
#             # Handle string representation of list
#             drop_columns = (
#                 eval(drop_columns) if drop_columns.startswith("[") else [drop_columns]
#             )
#         offers = offers.drop(columns=drop_columns, errors="ignore")
#         logger.info(f"Dropped columns: {drop_columns}")

#     # Apply sample limit
#     if config["input"].get("n_samples"):
#         n_samples = config["input"]["n_samples"]
#         offers = offers[:n_samples]
#         logger.info(f"Limited to {n_samples} samples")

#     logger.info(f"Loaded {len(offers)} offers with columns: {list(offers.columns)}")
#     return offers


def filter_offers_for_web_search(
    offers: pd.DataFrame, llm_results: pd.DataFrame, config: dict
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

            logger.info(f"Kept {len(filtered_offers)} offers that need verification")
            return filtered_offers
        else:
            logger.warning(
                "No valid condition or empty LLM results, keeping all offers"
            )

    logger.info(f"""Filtered {len(offers)} offers to {
        len(filtered_offers)} for web search""")
    return filtered_offers


def enrich_offers_with_llm_results(
    offers: pd.DataFrame, llm_results: pd.DataFrame
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
    logger.info(f"""New columns added: {[
        col for col in enriched_offers.columns if col.endswith('_llm_result')]}""")

    return enriched_offers


def run_validation_pipeline(config: dict, offers: pd.DataFrame) -> pd.DataFrame:
    """
    Execute the validation pipeline based on configuration.

    Args:
        config: Configuration dictionary
        offers: DataFrame of offers to validate

    Returns:
        Validation results DataFrame
    """
    validation_mode = config["validation"].get("mode", "llm_only")
    validation_config = config["validation"]

    if validation_mode == "llm_only":
        logger.info("Running LLM validation only...")
        results = get_llm_validation(offers, validation_config["llm_config"])

    # elif validation_mode == "web_search_only":
    #     logger.info("Running web search validation only...")
    #     results = get_web_check(
    #         offers,
    #         validation_config["web_search_config"],
    #         config["columns"]["price_to_check"],
    #     )

    elif validation_mode == "sequential_pipeline":
        logger.info("Running sequential LLM → Web Search pipeline...")

        # Step 1: Run initial LLM validation
        logger.info("Step 1: Initial LLM validation...")
        llm_results = get_llm_validation(offers, validation_config["llm_config"])
        logger.info(f"LLM validation completed: {len(llm_results)} results")

        # Step 2: Enrich offers with LLM results
        logger.info("Step 2: Enriching offers with LLM results...")
        enriched_offers = enrich_offers_with_llm_results(offers, llm_results)

        # Step 3: Run web search with enriched context
        logger.info("Step 3: Web search validation with LLM context...")
        web_results = get_web_check(
            enriched_offers,  # Pass enriched offers instead of original
            validation_config["web_search_config"],
            config["columns"]["price_to_check"],
        )

        # Step 4: Combine all results
        if not web_results.empty:
            # Start with LLM results and merge web results
            results = llm_results.merge(
                web_results,
                on="offer_id",
                how="left",
                suffixes=("_first_call", "_web_search"),
            )
            logger.info("Sequential pipeline results combined successfully")
        else:
            results = llm_results
            logger.info("No web search results, using initial LLM results only")

    # elif validation_mode == "both_separate":
    #     logger.info("Running both LLM and web search validations separately...")

    #     # Run LLM validation
    #     llm_results = get_llm_validation(offers, validation_config["llm_config"])
    #     logger.info(f"LLM validation completed: {len(llm_results)} results")

    #     # Run web search validation
    #     web_results = get_web_check(
    #         offers,
    #         validation_config["web_search_config"],
    #         config["columns"]["price_to_check"],
    #     )
    #     logger.info(f"Web search validation completed: {len(web_results)} results")

    #     # Merge results
    #     if not web_results.empty:
    #         results = llm_results.merge(
    #             web_results, on="offer_id", how="left", suffixes=("_llm", "_web")
    #         )
    #         logger.info("Results merged successfully")
    #     else:
    #         results = llm_results
    #         logger.info("No web search results to merge, using LLM results only")

    elif validation_mode == "conditional_web_search":
        logger.info("Running LLM validation with conditional web search...")

        # First run LLM validation
        llm_results = get_llm_validation(offers, validation_config["llm_config"])
        logger.info(f"LLM validation completed: {len(llm_results)} results")

        # Filter offers for web search based on LLM results
        filtered_offers = filter_offers_for_web_search(offers, llm_results, config)

        if not filtered_offers.empty:
            # Enrich filtered offers with LLM results before web search
            enriched_filtered = enrich_offers_with_llm_results(
                filtered_offers, llm_results
            )

            web_results = get_web_check(
                enriched_filtered,
                validation_config["web_search_config"],
                config["columns"]["price_to_check"],
            )
            logger.info(f"Web search validation completed: {len(web_results)} results")

            # Merge results
            results = llm_results.merge(
                web_results, on="offer_id", how="left", suffixes=("_llm", "_web")
            )
        else:
            results = llm_results
            logger.info("No offers met criteria for web search")

    else:
        raise ValueError(f"Unknown validation mode: {validation_mode}")

    return results


# def save_results_and_logs(results: pd.DataFrame, config: dict):
#     """Save results and setup logging directories."""
#     # Create output directories
#     output_path = Path(config["output"].get("results_path", "validation_results.csv"))
#     output_path.parent.mkdir(parents=True, exist_ok=True)

#     log_dir = Path(config["output"].get("log_dir", "logs"))
#     log_dir.mkdir(parents=True, exist_ok=True)

#     # Save results
#     results.to_csv(output_path, index=False)
#     logger.info(f"Results saved to: {output_path}")

#     return output_path, log_dir


# def print_summary(
#     offers: pd.DataFrame, results: pd.DataFrame, output_path: Path, log_dir: Path
# ):
#     """Print validation summary statistics."""
#     print("\n" + "=" * 50)
#     print("VALIDATION RESULTS SUMMARY")
#     print("=" * 50)
#     print(f"Total offers processed: {len(offers)}")
#     print(f"Results generated: {len(results)}")
#     print(f"Results saved to: {output_path}")
#     print(f"Logs saved to: {log_dir}")

#     # Show web search specific stats if available
#     if "web_search_performed" in results.columns:
#         web_searches_performed = results["web_search_performed"].sum()
#         print("\nWeb Search Statistics:")
#         print(f"Web searches performed: {web_searches_performed}")
#         if web_searches_performed > 0:
#             success_rate = (
#                 results["web_search_error"].isna().sum() / web_searches_performed
#             ) * 100
#             print(f"Success rate: {success_rate:.1f}%")

#     # Show sample results
#     print("\nSample Results:")
#     print(results.head().to_string())


# def run_validation(config_path: str | None = None):
#     """
#     Main validation orchestrator function.

#     Args:
#         config_path: Optional path to config file. If not provided, uses default config.
#     """
#     try:
#         # Load configuration
#         config = load_config(config_path)
#         logger.info(f"Configuration loaded from: {config_path or 'default config'}")

#         # Setup environment
#         setup_environment()

#         # Load and prepare data
#         offers = load_data(config)

#         # Run validation pipeline
#         results = run_validation_pipeline(config, offers)

#         # Save results and setup logging
#         output_path, log_dir = save_results_and_logs(results, config)

#         # Print summary
#         print_summary(offers, results, output_path, log_dir)

#         logger.info("Validation pipeline completed successfully!")

#     except Exception as e:
#         logger.error(f"Validation pipeline failed: {e}")
#         raise


# if __name__ == "__main__":
#     import argparse

#     parser = argparse.ArgumentParser(
#         description="Run unified LLM and web search validation pipeline"
#     )
#     parser.add_argument("--config", help="Path to YAML configuration file", type=str)
#     args = parser.parse_args()

#     run_validation(args.config)

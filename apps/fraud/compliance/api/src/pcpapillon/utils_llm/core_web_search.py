from typing import Any

import pandas as pd
from loguru import logger
from pcpapillon.utils_llm.config_manager import config_manager
from pcpapillon.utils_llm.parser import create_output_parser
from pcpapillon.utils_llm.prompt_manager import get_prompt_template
from pcpapillon.utils_llm.tools.logging_utils import log_llm_prompt
from pcpapillon.utils_llm.web_search_utils import (
    get_web_search_chain,
    should_perform_web_search,
)
from tqdm import tqdm


def _process_web_search_result(
    offer_data: dict[str, Any],
    parsed_result: dict[str, Any],
    search_params: dict[str, Any],
) -> dict[str, Any]:
    base_result = {
        "offer_id": offer_data.get("offer_id"),
        "stock_price": offer_data.get("stock_price"),
    }

    # Simply flatten the parsed result
    if isinstance(parsed_result, dict):
        base_result.update(parsed_result)
    else:
        base_result["web_search_result"] = parsed_result

    return base_result


def run_web_search_validation(
    offers: pd.DataFrame,
    config,
    web_search_chain,
    format_instructions: str,
    response_schemas: dict,
    price_to_check: str | None,
    validation_result: dict[str, Any],
) -> pd.DataFrame:
    """
    Execute web search validation with optional LLM context.
    """

    if offers.empty:
        raise ValueError("Offers DataFrame is empty")

    logger.info(f"Starting web search validation of {len(offers)} offers")
    web_search_results = []

    # Check if offers contain LLM context
    has_llm_context = any(col.endswith("_llm_result") for col in offers.columns)
    if has_llm_context:
        logger.info("Using LLM context for enhanced web search")

    output_parser = create_output_parser(config, response_schemas)
    comparison_price = price_to_check

    try:
        for _, offer in tqdm(
            offers.iterrows(), total=len(offers), desc="Web searching offers"
        ):
            columns = [
                "offer_id",
                "offer_name",
                "offer_description",
                "offer_subcategory_id",
            ]
            if comparison_price:
                columns.append(comparison_price)
            offre_commerciale = offer[columns].to_dict()

            # Extract LLM context if available
            llm_context = {}
            if has_llm_context:
                llm_context = {
                    col.replace("_llm_result", ""): offer[col]
                    for col in offer.index
                    if col.endswith("_llm_result") and pd.notna(offer[col])
                }

            # Vérifier si on doit faire la recherche pour cette offre
            if not should_perform_web_search(config):
                logger.info(
                    f"Skipping web search for offer {offre_commerciale.get('offer_id')}"
                )
                continue

            try:
                # Préparer les paramètres de recherche
                search_params = {
                    "offer_name": offre_commerciale.get("offer_name"),
                    "reference_sites": config.reference_sites,
                    "comparison_price": offre_commerciale.get(
                        price_to_check, None
                    ),  # prix de la participation extrait ici du validation_result
                    "format_instructions": format_instructions,
                }

                # Add LLM context to search parameters
                if llm_context:
                    search_params.update(
                        {
                            "llm_extracted_price": llm_context.get("extracted_price"),
                            "llm_confidence": llm_context.get("confidence_score"),
                            "llm_category": llm_context.get("product_category"),
                            "llm_analysis": llm_context.get("analysis_summary"),
                            "context_enhanced": True,
                        }
                    )
                else:
                    search_params["context_enhanced"] = False

                # Log de la recherche web
                log_llm_prompt(
                    prompt=f"Web search for: {search_params['offer_name']}",
                    config=config.dict() if hasattr(config, "dict") else vars(config),
                    offer_id=offre_commerciale.get("offer_id"),
                    metadata={
                        "reference_sites": search_params.get("reference_sites"),
                        "comparison_price": search_params.get("comparison_price"),
                        "has_llm_context": bool(llm_context),
                        "llm_context_fields": list(llm_context.keys())
                        if llm_context
                        else [],
                    },
                )

                # Exécuter la recherche web
                result = web_search_chain.invoke(search_params)
                parsed_result = output_parser.parse(result)
                logger.info(
                    f"""Web search result for
                    {offre_commerciale.get("offer_id")}: {parsed_result}"""
                )

                # Traiter le résultat
                processed_result = _process_web_search_result(
                    offre_commerciale,
                    parsed_result,
                    search_params,
                )

                web_search_results.append(processed_result)

                # Convert results to DataFrame
                web_search_result_df = pd.DataFrame(web_search_results)

            except Exception as e:
                logger.error(
                    f"""Error in web search for offer
                    {offre_commerciale.get("offer_id")}: {e}"""
                )
                # Ajouter une ligne d'erreur
                error_row = pd.DataFrame(
                    [
                        {
                            "offer_id": offre_commerciale.get("offer_id"),
                            "offer_name": offre_commerciale.get("offer_name"),
                            "web_search_performed": False,
                            "web_search_error": str(e),
                            "web_search_result": None,
                            # "used_llm_context": bool(llm_context),
                        }
                    ]
                )
                web_search_result_df = pd.concat(
                    [web_search_result_df, error_row], ignore_index=True
                )

        logger.info("Successfully completed web search validation")
        return web_search_result_df

    except Exception as e:
        logger.error(f"Error during web search validation: {e!s}")
        raise


def get_web_check(
    offers: pd.DataFrame, config_name: str, price_to_check: str
) -> pd.DataFrame:
    """
    Perform web search validation of offers using configuration.
    Mirrors the structure of get_llm_validation.

    Args:
        offers (pd.DataFrame): DataFrame containing offers to validate
        config_name (str): Name of the configuration to use

    Returns:
        pd.DataFrame: Results of the web search validation

    Raises:
        ValueError: If the configuration is invalid or not found
        Exception: For other validation errors
    """
    try:
        # Get configuration
        config = config_manager.get_config(config_name)
        schema = config_manager.get_schema(config.schema_type)
        format_instructions = create_output_parser(
            config, schema
        ).get_format_instructions()

        # Vérifier si la recherche web est activée
        if not getattr(config, "web_search", False):
            logger.info(f"Web search disabled for config {config_name}")
            return pd.DataFrame()  # Retourner un DataFrame vide

    except Exception as e:
        logger.error(f"Error in web search validation 1: {e!s}")
        raise

    try:
        # Créer la chaîne de recherche web
        langchain_prompt = get_prompt_template(config, schema)
        chain = get_web_search_chain(config, langchain_prompt)

    except Exception as e:
        logger.error(f"Error in web search validation 2: {e!s}")
        raise

    try:
        # Exécuter la recherche web
        web_search_result_df = run_web_search_validation(
            offers,
            config,
            chain,
            format_instructions,
            schema,
            price_to_check if price_to_check else None,
            validation_result={},
            # validation_result est un dictionnaire vide ici, car on n'a pas de résultat
            # de validation précédent
        )
        return web_search_result_df

    except Exception as e:
        logger.error(f"Error in web search validation 3: {e!s}")
        raise

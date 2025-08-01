"""
Core functionality for the LLM framework.
"""

import pandas as pd
from config_manager import config_manager
from llm_manager import get_llm_chain
from loguru import logger
from models import LLMConfig
from parser import create_output_parser, post_process_result
from prompt_manager import get_prompt_template
from tools.logging_utils import log_llm_prompt
from tqdm import tqdm
from validators import get_txt_from_path
from rules.subcategory_rules_mapping import get_rules_file


def run_global_validation(
    offers: pd.DataFrame,
    config: LLMConfig,
    chain,
    regles_conformite: str | None,
    format_instructions: str,
    response_schemas: dict,
) -> pd.DataFrame:
    """
    Execute validation on multiple offers and return results, supports enriched context
    from previous LLM results.

    Args:
        offers (pd.DataFrame): DataFrame containing offers to validate
        config (LLMConfig): Configuration for the validation
        chain: Initialized LLM chain
        regles_conformite (str): Compliance rules
        format_instructions (str): Format instructions for the LLM
        response_schemas (Dict): Response schemas for parsing

    Returns:
        pd.DataFrame: Results of the validation

    Raises:
        ValueError: If offers DataFrame is empty or invalid
        Exception: For other validation errors
    """
    if offers.empty:
        raise ValueError("Offers DataFrame is empty")

    logger.info(f"Starting validation of {len(offers)} offers")
    validation_result_df = pd.DataFrame()
    output_parser = create_output_parser(config, response_schemas)

    # Check if offers contain previous LLM results (enriched context)
    has_llm_context = any(col.endswith("_llm_result") for col in offers.columns)
    if has_llm_context:
        logger.info("Detected LLM context in offers - using enriched validation")

    try:
        for idx, offer in tqdm(
            offers.iterrows(), total=len(offers), desc="Validating offers"
        ):
            try:
                # Extract offer details
                offre_commerciale = offer[
                    ["offer_id", "offer_name", "offer_description", "last_stock_price",
                     "offer_subcategory_id"]
                ].to_dict()

                # Add LLM context if available
                llm_context = {}
                if has_llm_context:
                    llm_context = {
                        col: offer[col]
                        for col in offer.index
                        if col.endswith("_llm_result") and pd.notna(offer[col])
                    }
                    logger.debug(
                        f"""LLM context for offer {offre_commerciale[
                            'offer_id']}: {llm_context}"""
                    )

                # Get the rendered prompt before making the call
                prompt_args = {
                    "regles_conformite": regles_conformite
                    if regles_conformite is not None
                    else "",
                    "offre_commerciale": offre_commerciale,
                    "format_instructions": format_instructions,
                }

                # Add LLM context to prompt if available
                if llm_context:
                    prompt_args["previous_analysis"] = llm_context
                    prompt_args["context_available"] = True
                else:
                    prompt_args["context_available"] = False

                rendered_prompt = chain.prompt.format(**prompt_args)

                subcat_id = offers.loc[0, "offer_subcategory_id"]
                # Log the prompt with metadata
                log_llm_prompt(
                    prompt=rendered_prompt,
                    config=config.dict() if hasattr(config, "dict") else vars(config),
                    offer_id=offre_commerciale.get("offer_id"),
                    metadata={
                        "rules_file": get_rules_file(subcat_id),
                        "prompt_type": config.prompt_type
                        if hasattr(config, "prompt_type")
                        else config.get("prompt_type"),  # type: ignore
                        "has_llm_context": has_llm_context,
                        "llm_context_fields": list(llm_context.keys())
                        if llm_context
                        else [],
                    },
                )

                # Make the LLM call
                result = chain.run(**prompt_args)

                try:
                    # Tentative de parsing normal
                    parsed_result = output_parser.parse(result)
                    logger.info(f"result: {parsed_result}")
                    clean_result_df = post_process_result(
                        config, offre_commerciale, parsed_result, response_schemas
                    )
                    validation_result_df = pd.concat(
                        [validation_result_df, clean_result_df]
                    )

                except Exception as parse_error:
                    logger.warning(
                        f"""Échec du parsing JSON pour l'offre {offre_commerciale.get(
                            'offer_id', 'unknown')}: {parse_error}"""
                    )
                    logger.info(f"Résultat brut sauvegardé: {result}")

                    # Fallback: créer un DataFrame avec le résultat brut
                    fallback_data = {
                        "offer_id": [offre_commerciale.get("offer_id", "unknown")],
                        "raw_result": [str(result)],
                        "parsing_error": [str(parse_error)],
                        "timestamp": [pd.Timestamp.now()],
                        "status": ["parsing_failed"],
                    }

                    fallback_df = pd.DataFrame(fallback_data)
                    validation_result_df = pd.concat(
                        [validation_result_df, fallback_df], ignore_index=True
                    )

                    logger.info(
                        f"""Données sauvegardées avec fallback pour l'offre {
                            offre_commerciale.get('offer_id', 'unknown')}"""
                    )

            except Exception as offer_error:
                logger.error(
                    f"""Erreur lors du traitement de l'offre {offer.get(
                        'offer_id', idx)}: {offer_error}"""
                )

                # Créer une entrée d'erreur pour cette offre
                error_data = {
                    "offer_id": [offer.get("offer_id", f"unknown_{idx}")],
                    "raw_result": [""],
                    "processing_error": [str(offer_error)],
                    "timestamp": [pd.Timestamp.now()],
                    "status": ["processing_failed"],
                }

                error_df = pd.DataFrame(error_data)
                validation_result_df = pd.concat(
                    [validation_result_df, error_df], ignore_index=True
                )

                logger.info(
                    f"Erreur enregistrée pour l'offre {offer.get('offer_id', idx)}"
                )
                continue

        logger.info("Successfully completed validation")
        return validation_result_df

    except Exception as e:
        logger.error(f"Error during global validation: {e!s}")

        # Sauvegarde d'urgence avant de lever l'exception
        emergency_save_path = (
            f"emergency_backup_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )
        if not validation_result_df.empty:
            validation_result_df.to_csv(emergency_save_path, index=False)
            logger.info(f"Sauvegarde d'urgence effectuée: {emergency_save_path}")

        raise


def get_llm_validation(offers: pd.DataFrame, config_name: str) -> pd.DataFrame:
    """
    Perform validation of offers using an LLM according to the specified configuration.

    Args:
        offers (pd.DataFrame): DataFrame containing offers to validate
        config_name (str): Name of the configuration to use

    Returns:
        pd.DataFrame: Results of the validation

    Raises:
        ValueError: If the configuration is invalid or not found
        Exception: For other validation errors
    """
    try:
        # Get configuration and schema
        config = config_manager.get_config(config_name)
        schema = config_manager.get_schema(config.schema_type)
    except Exception as e:
        logger.error(f"Error in LLM validation 1: {e!s}")
        raise
    try:
        # Create prompt template and chain
        prompt_template = get_prompt_template(config, schema)
        chain = get_llm_chain(config, prompt_template)
    except Exception as e:
        logger.error(f"Error in LLM validation 2: {e!s}")
        raise
    try:
        # Get rules and format instructions
        subcat_id = offers.loc[0, "offer_subcategory_id"]
        rules_file = get_rules_file(subcat_id)

        if rules_file:
            regles_conformite = get_txt_from_path("rules", rules_file)
        else:
            regles_conformite = ""
            logger.info(f"""No rules file specified in configuration for subcategory: {
                subcat_id}""")
        format_instructions = create_output_parser(
            config, schema
        ).get_format_instructions()
    except Exception as e:
        logger.error(f"Error in LLM validation 3: {e!s}")
        raise
    try:
        # Run validation
        validation_result_df = run_global_validation(
            offers, config, chain, regles_conformite, format_instructions, schema
        )
        return validation_result_df
    except Exception as e:
        logger.error(f"Error in LLM validation 4: {e!s}")
        raise
        # return validation_result_df

    except Exception as e:  # noqa: B025
        logger.error(f"Error in LLM validation: {e!s}")
        raise

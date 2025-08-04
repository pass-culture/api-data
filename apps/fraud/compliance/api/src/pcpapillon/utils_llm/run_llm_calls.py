"""
Unified validation orchestrator supporting both LLM and web search validation.
"""

import pandas as pd
from loguru import logger

# Import both validation modules
from pcpapillon.utils_llm.core import get_llm_validation
from pcpapillon.utils_llm.core_web_search import get_web_check


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

def synthese_validation_finale(llm_results: pd.DataFrame, web_results: pd.DataFrame,
                               config: dict) -> pd.DataFrame:
    """
    Synthesize final validation results combining LLM compliance and web search

    Args:
        llm_results: Results from LLM validation
        web_results: Results from web search validation
        config: Configuration dictionary containing price thresholds

    Returns:
        DataFrame with final synthesized validation results
    """
    logger.info("Step 4: Synthesizing final validation results...")

    # Get price divergence threshold from config (default to 20% if not specified)
    price_threshold = config["validation"].get("price_divergence_threshold", 10.0)

    # Start with a copy of LLM results
    final_results = llm_results.copy()

    # Add columns for final synthesis
    final_results['réponse_LLM_finale'] = final_results['Réponse_llm']
    final_results['explication_finale'] = final_results['Explication_classification']
    final_results['validation_source'] = 'llm_only'

    if not web_results.empty:
        # Merge web search results
        final_results = final_results.merge(
            web_results[['offer_id', 'pourcentage_divergence_prix',
                         'prix_moyen', 'liens_source']],
            on='offer_id',
            how='left'
        )

        # Process each offer for final decision
        for idx, row in final_results.iterrows():
            llm_decision = row['Réponse_llm']

            # If already rejected by LLM, keep the rejection
            if llm_decision.lower() in ['rejected', 'rejete']:
                final_results.at[idx, 'validation_source'] = 'llm_rejection'
                continue

            # If approved by LLM, check web search results
            if not pd.isna(row.get('pourcentage_divergence_prix')):
                price_divergence = row['pourcentage_divergence_prix']
                prix_moyen = row.get('prix_moyen', 'N/A')

                if price_divergence > price_threshold:
                    # Reject due to overpricing
                    final_results.at[idx, 'réponse_LLM_finale'] = 'rejected'
                    final_results.at[idx, 'explication_finale'] = (
                        f"""Offre conforme aux règles de conformité mais prix surévalué
                        de {price_divergence:.1f}% par rapport au marché (seuil:
                        {price_threshold}%). Prix moyen du marché: {prix_moyen}."""
                    )
                    final_results.at[idx, 'validation_source'] = 'surtarification_web'
                else:
                    # Approve with price validation
                    final_results.at[idx, 'réponse_LLM_finale'] = 'approved'
                    final_results.at[idx, 'explication_finale'] = (
                        f"""{row['Explication_classification']}. Prix cohérent avec le
                        marché (divergence: {price_divergence:.1f}%)."""
                    )
                    final_results.at[idx, 'validation_source'] = 'llm_and_web_approved'
            else:
                # No web search performed, keep LLM decision
                final_results.at[idx, 'validation_source'] = 'llm_only'

    # Log synthesis results
    synthesis_stats = final_results['validation_source'].value_counts()
    logger.info("Synthèse finale réalisée")
    for source, count in synthesis_stats.items():
        logger.info(f"  - {source}: {count} offers")

    return final_results


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

    elif validation_mode == "sequential_pipeline":
        logger.info("Running sequential LLM → Web Search pipeline...")

        # Step 1: Run initial LLM validation
        logger.info("Step 1: LLM validation pour toutes les offres...")
        llm_results = get_llm_validation(offers, validation_config["llm_config"])
        logger.info(f"LLM validation completed: {len(llm_results)} results")

        # Step 2: Filtre des offres pour n'amener en web search que celles approved par
        # le premier appel au LLM")
        logger.info("Step 2: Filtering offers approved by the LLM for web search...")

        approved_values = ['ACCEPTED', 'approved', 'APPROVED', 'accepted']
        approved_llm_results = llm_results[llm_results['Réponse_llm'].isin(
            approved_values)]

        # Merge to get the original offers that were approved
        offers_to_web_check = offers.merge(
            approved_llm_results[['offer_id']],
            on='offer_id',
            how='inner'
        )

        logger.info(f"{len(offers_to_web_check)} offers to be sent for web search.")

        # Step 3: Run web search only for the filtered, enriched offers
        web_results = pd.DataFrame()
        if not offers_to_web_check.empty:
            logger.info("Step 3: Running web search for approved offers...")

            # Enrich the offers to be checked with the LLM results
            logger.info("Step 2: Enriching offers with LLM results...")
            enriched_offers = enrich_offers_with_llm_results(offers_to_web_check,
                                                             approved_llm_results)

            web_results = get_web_check(
                enriched_offers,
                validation_config["web_search_config"],
                config["columns"]["price_to_check"],
            )
            logger.info("Web search completed.")
        else:
            logger.warning("No offers were approved by the LLM, skipping web search.")

        # Step 4: NEW - Synthesize final results
        results = synthese_validation_finale(llm_results, web_results, config)
        logger.info("Sequential pipeline with synthesis completed successfully")

    else:
        raise ValueError(f"Unknown validation mode: {validation_mode}")

    return results

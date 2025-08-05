"""
Response parsing utilities for LLM outputs.
"""

import pandas as pd
from langchain.output_parsers.structured import ResponseSchema, StructuredOutputParser

from pcpapillon.utils_llm.rules.subcategory_rules_mapping import get_rules_file


def create_output_parser(config, response_schemas):
    """Creates a structured parser for LLM responses based on the specified schema."""

    response_schemas_parsed = []
    for schema in response_schemas:
        response_schemas_parsed.append(
            ResponseSchema(
                name=schema.get("name"),
                description=schema.get("description", ""),
                type=schema.get("type", "string"),
            )
        )

    return StructuredOutputParser.from_response_schemas(response_schemas_parsed)

def post_process_result(config, offre_commerciale, result, response_schemas):
    """Process raw LLM result and format it as a DataFrame based on the schema used."""

    offer_id = offre_commerciale.get("offer_id")
    subcat_id = offre_commerciale.get("offer_subcategory_id")
    nom_produit = offre_commerciale.get("offer_name")
    description = offre_commerciale.get("offer_description")
    prix = offre_commerciale.get("last_stock_price")

    # Get provider and model from config
    provider = config.get("provider") if isinstance(config, dict) else config.provider
    model = config.get("model") if isinstance(config, dict) else config.model
    regles = get_rules_file(subcat_id)
    prompt_type = (
        config.get("prompt_type") if isinstance(config, dict) else config.prompt_type
    )

    # Colonnes de base communes à tous les schémas
    base_columns = {
        "offer_id": [offer_id],
        "model": [f"{provider}/{model}"],
        "rule": [regles],
        "prompt": [prompt_type],
        "offer": [nom_produit],
        "description": [description],
        "price": [prix],
    }

    # Colonnes spécifiques au schéma utilisé
    schema_columns = {}

    for schema in response_schemas:
        field_name = schema.get("name")
        value = result.get(field_name)
        schema_columns[field_name] = [value]

    # Fusionner les colonnes de base et spécifiques
    all_columns = {**base_columns, **schema_columns}
    df = pd.DataFrame(all_columns)

    return df

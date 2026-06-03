"""
Response parsing utilities for LLM outputs.
"""

import pandas as pd
from langchain_core.output_parsers.json import JsonOutputParser

from pcpapillon.utils_llm.rules.subcategory_rules_mapping import get_rules_file


class ComplianceJsonOutputParser(JsonOutputParser):
    """Custom JSON output parser that provides format instructions for LLM."""

    def __init__(self, response_schemas, **kwargs):
        super().__init__(**kwargs)
        # Store schemas in __dict__ to avoid Pydantic field validation
        self.__dict__["_response_schemas"] = response_schemas

    def get_format_instructions(self) -> str:
        """Generate format instructions based on the response schemas."""
        response_schemas = self.__dict__.get("_response_schemas", [])
        schema_desc = []
        for schema in response_schemas:
            name = schema.get("name")
            desc = schema.get("description", "")
            field_type = schema.get("type", "string")
            schema_desc.append(f'  "{name}": <{field_type}> - {desc}')

        schema_str = ",\n".join(schema_desc)

        return f"""Respond with a valid JSON object with the following structure:
{{
{schema_str}
}}

IMPORTANT: 
- Respond ONLY with the JSON object, no additional text before or after
- Ensure all string values are properly escaped
- Use double quotes for JSON keys and string values"""


def create_output_parser(config, response_schemas):
    """Creates a structured parser for LLM responses based on the specified schema."""
    # For langchain 1.x, we use our custom JsonOutputParser with format instructions
    return ComplianceJsonOutputParser(response_schemas)


def post_process_result(config, offre_commerciale, result, response_schemas):
    """Process raw LLM result and format it as a DataFrame based on the schema used."""

    offer_id = offre_commerciale.get("offer_id")
    subcat_id = offre_commerciale.get("offer_subcategory_id")
    nom_produit = offre_commerciale.get("offer_name")
    description = offre_commerciale.get("offer_description")
    prix = offre_commerciale.get("stock_price")

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

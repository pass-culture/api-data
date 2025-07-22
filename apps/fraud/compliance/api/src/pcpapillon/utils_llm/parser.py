"""
Response parsing utilities for LLM outputs.
"""

import json

import pandas as pd
from langchain.output_parsers.structured import ResponseSchema, StructuredOutputParser
from loguru import logger


def create_output_parser(config, response_schemas):
    """Creates a structured parser for LLM responses based on the specified schema."""

    # # For simple yes/no validation (rules type), create a basic schema
    # schema_type = (
    #     config.get("schema_type") if isinstance(config, dict) else config.schema_type
    # )

    # Conversion des dictionnaires en objets ResponseSchema
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


def parse_examples(examples_str):
    """Parse multiple dictionaries from a string in the same text
    file for few-shot prompts."""
    # Diviser la chaîne en exemples individuels - suppose que les exemples sont séparés
    # par des lignes vides
    raw_examples = examples_str.split("\n\n")

    parsed_examples = []
    for example in raw_examples:
        if example.strip():  # Ignorer les lignes vides
            # Remplacer les apostrophes par des guillemets
            example = example.replace("'", '"')

            # Quelques corrections courantes
            example = example.replace("None", "null")

            # Utiliser json pour parser
            try:
                parsed_example = json.loads(example)
                parsed_examples.append(parsed_example)
            except json.JSONDecodeError as e:
                logger.error(f"Erreur de parsing JSON: {e}\nExemple: {example}")

    return parsed_examples


def parse_simple_response(response: str) -> dict:
    """Parse a simple yes/no response into a dictionary format.

    Args:
        response: The raw response from the LLM

    Returns:
        A dictionary with the parsed response
    """
    # Clean and normalize the response
    response = response.strip().lower()

    # Map variations of yes/no responses
    yes_variants = {"yes", "oui", "true", "1", "vrai"}
    no_variants = {"no", "non", "false", "0", "faux"}

    if response in yes_variants:
        result = "oui"
    elif response in no_variants:
        result = "non"
    else:
        logger.warning(f"Unexpected response: {response}. Expected yes/no.")
        result = response

    return {"validation": result}


def post_process_result(config, offre_commerciale, result, response_schemas):
    """Process raw LLM result and format it as a DataFrame based on the schema used."""
    schema_type = (
        config.get("schema_type") if isinstance(config, dict) else config.schema_type
    )

    # If this is a simple yes/no response (rules schema)
    if schema_type == "rules" and isinstance(result, str):
        result = parse_simple_response(result)
    elif isinstance(result, str):
        try:
            result = json.loads(result)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}\nResponse: {result}")
            result = {"error": str(e), "raw_response": result}

    offer_id = offre_commerciale.get("offer_id")
    nom_produit = offre_commerciale.get("offer_name")
    description = offre_commerciale.get("offer_description")
    prix = offre_commerciale.get("last_stock_price")

    # Get provider and model from config
    provider = config.get("provider") if isinstance(config, dict) else config.provider
    model = config.get("model") if isinstance(config, dict) else config.model
    regles = config.get("regles") if isinstance(config, dict) else config.regles
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
        schema_columns[field_name.capitalize()] = [value]

    # Fusionner les colonnes de base et spécifiques
    all_columns = {**base_columns, **schema_columns}
    df = pd.DataFrame(all_columns)

    return df

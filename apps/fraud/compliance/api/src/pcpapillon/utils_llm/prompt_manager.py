"""
Prompt creation and management utilities.
"""

from langchain_core.prompts import ChatPromptTemplate

from pcpapillon.utils_llm.validators import get_txt_from_path


def get_prompt_template(config, response_schemas):
    """
    Creates a prompt template based on configuration
    => supports simple and few-shot prompts.
    """
    prompt_type = (
        config["prompt_type"] if isinstance(config, dict) else config.prompt_type
    )
    prompt = get_txt_from_path("prompt", prompt_type)

    if prompt_type in ("base"):
        prompt_template = ChatPromptTemplate.from_template(
            prompt
            + """
            <rules>
            {regles_conformite}
            </rules>

            <offer>
            {offre_commerciale}
            </offer>

            <instructions>
            Analyse l'offre commerciale selon les règles de conformité fournies et
            réponds au format suivant :
            </instructions>

            <format>
            {format_instructions}
            </format>
            """
        )

    elif prompt_type == "web_search_prix":
        prompt_template = ChatPromptTemplate.from_template(
            prompt
            + """
            <product>
            {offer_name}
            </product>

            <reference_sites>
            {reference_sites}
            </reference_sites>

            <comparison_price>
            {comparison_price}
            </comparison_price>

            <instructions>
            Réponds au format suivant :
            </instructions>

            <format>
            {format_instructions}
            </format>
            """
        )

    return prompt_template

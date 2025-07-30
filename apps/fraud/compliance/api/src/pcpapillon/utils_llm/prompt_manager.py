"""
Prompt creation and management utilities.
"""

from langchain_core.prompts import ChatPromptTemplate, FewShotChatMessagePromptTemplate
# from parser import parse_examples
from validators import get_txt_from_path


# def create_few_shot_prompt(examples, regles, config, response_schemas):
#     """Creates a few-shot prompt template from multiple examples."""
#     # Parse the examples
#     parsed_examples = parse_examples(examples)
#     schema_type = (
#         config["schema_type"] if isinstance(config, dict) else config.schema_type
#     )

#     # Prepare examples according to the selected schema
#     processed_examples = []

#     # Create few-shot prompt based on the Response Schema
#     for parsed_example in parsed_examples:
#         # Prepare the response based on available fields
#         reponse_parts = []
#         for schema in response_schemas.get(schema_type):
#             field_name = schema.get("name")
#             if field_name in parsed_example:
#                 reponse_parts.append(
#                     f"{field_name.capitalize()}: {parsed_example.get(field_name)}"
#                 )

#         processed_examples.append(
#             {
#                 "regles": regles,
#                 "offre": f"""Nom: {parsed_example.get("offer_name")}
#                 Description: {parsed_example.get("offer_description")}
#                 Prix: {parsed_example.get("last_stock_price")}""",
#                 "reponse": "\n".join(reponse_parts),
#             }
#         )

#     # Create example prompt template
#     # example_prompt = ChatPromptTemplate.from_messages(
#     #     [
#     #         (
#     #             "user",
#     #             "Règles de conformité:\n{regles}\n\n"
#     #             "Offre commerciale à analyser:\n{offre}",
#     #         ),
#     #         ("assistant", "{reponse}"),
#     #     ]
#     # )

#     example_prompt = ChatPromptTemplate.from_messages(
#         [
#             (
#                 "user",
#                 "<rules>\n{regles}\n</rules>\n\n" "<offer>\n{offre}\n</offer>",
#             ),
#             ("assistant", "{reponse}"),
#         ]
#     )

#     few_shot_prompt = FewShotChatMessagePromptTemplate(
#         examples=processed_examples, example_prompt=example_prompt
#     )

#     return few_shot_prompt


def get_prompt_template(config, response_schemas):
    """
    Creates a prompt template based on configuration
    => supports simple and few-shot prompts.
    """
    prompt_type = (
        config["prompt_type"] if isinstance(config, dict) else config.prompt_type
    )
    prompt = get_txt_from_path("prompt", prompt_type)

    # Create output parser instructions
    # output_parser = create_output_parser(config, response_schemas) => Not used
    # format_instructions = output_parser.get_format_instructions() => Not used

    if prompt_type in ("base"
                    #    , "rules", "test_agent"
                    ):
        prompt_template = ChatPromptTemplate.from_template(
            prompt
            # + """
            # Règles de conformité:
            # {regles_conformite}
            # Offre commerciale à analyser:
            # {offre_commerciale}
            # Analyse l'offre selon les règles et réponds au format suivant:
            # {format_instructions}
            # """
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
    # elif prompt_type == "few_shot":
    #     examples_name = (
    #         config["examples"] if isinstance(config, dict) else config.examples
    #     )
    #     regles_name = config["regles"] if isinstance(config, dict) else config.regles

    #     examples = get_txt_from_path("exemples", examples_name)
    #     regles = get_txt_from_path("rules", regles_name)
    #     few_shot = create_few_shot_prompt(examples, regles, config, response_schemas)
    #     prompt_template = ChatPromptTemplate.from_messages(
    #         [
    #             ("system", prompt),
    #             few_shot,
    #             (
    #                 "human",
    #                 # """
    #                 # Règles de conformité:
    #                 # {regles_conformite}
    #                 # Offre commerciale à analyser:
    #                 # {offre_commerciale}
    #                 # Analyse l'offre selon les règles et réponds au format suivant:
    #                 # {format_instructions}
    #                 # """,
    #                 """
    #         <rules>
    #         {regles_conformite}
    #         </rules>

    #         <offer>
    #         {offre_commerciale}
    #         </offer>

    #         <instructions>
    #         Analyse l'offre selon les règles et réponds au format suivant :
    #         </instructions>

    #         <format>
    #         {format_instructions}
    #         </format>
    #         """,
    #             ),
    #         ]
    #     )
    elif prompt_type == "web_search_prix":
        # reference_sites = get_txt_from_path("reference_sites", config.reference_sites)
        prompt_template = ChatPromptTemplate.from_template(
            prompt
            # + """
            # Produit à rechercher: {offer_name}
            # Sites de références suivants : {reference_sites}
            # Prix proposé avec lequel comparé chez nous : {comparison_price}
            # Réponds au format suivant: {format_instructions}
            # """
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
    # elif prompt_type == "metadonnees_livres":
    #     prompt_template = ChatPromptTemplate.from_template(
    #         prompt
    #         + """
    #         <product>
    #         {offer_name}
    #         </product>

    #         <instructions>
    #         Réponds au format suivant :
    #         </instructions>

    #         <format>
    #         {format_instructions}
    #         </format>
    #         """
    #     )

    return prompt_template

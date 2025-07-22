# from langchain import LLMChain
from langchain.chat_models import init_chat_model
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from models import LLMConfig

# importer LLMConfig (config)


def get_web_search_chain(config: LLMConfig, langchain_prompt: ChatPromptTemplate):
    # -> LLMChain:
    # Get web search template and model from the configuration
    # template = config.web_search_template
    model = config.model
    llm = init_chat_model(
        model=f"openai:{model}",
        web_search_options={
            "user_location": {
                "type": "approximate",
                "approximate": {
                    "country": "FR",
                    "city": "Paris",
                    "region": "Paris",
                },  # éventuellement à adapter à la configuration
            }
        },
    )
    # prompt = ChatPromptTemplate.from_template(template)
    prompt = langchain_prompt
    output_parser = StrOutputParser()

    # Création de la chaîne
    chain = prompt | llm | output_parser
    return chain


def should_perform_web_search(config):
    return config.web_search


# on peut ajouter des conditions supplémentaires pour activer la web search, notamment
# selon l'output du premier LLM.

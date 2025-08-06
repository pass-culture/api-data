from langchain.chat_models import init_chat_model
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pcpapillon.utils_llm.models import LLMConfig

# importer LLMConfig (config)


def get_web_search_chain(config: LLMConfig, langchain_prompt: ChatPromptTemplate):
    # Get web search template and model from the configuration
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
                },
            }
        },
    )
    prompt = langchain_prompt
    output_parser = StrOutputParser()

    # Création de la chaîne
    chain = prompt | llm | output_parser
    return chain


def should_perform_web_search(config):
    return config.web_search

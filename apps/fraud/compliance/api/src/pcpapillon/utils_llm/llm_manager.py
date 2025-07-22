"""
LLM initialization and management.
"""

import json

from langchain import LLMChain
from langchain.chat_models import init_chat_model
from langchain_core.prompts import ChatPromptTemplate
from langchain_huggingface import HuggingFaceEndpoint
from loguru import logger
from models import LLMConfig


def get_llm_chain(config: LLMConfig, langchain_prompt: ChatPromptTemplate) -> LLMChain:
    """
    Create an LLMChain from the provided configuration and prompt.

    Args:
        config (LLMConfig): Configuration for the LLM
        langchain_prompt (ChatPromptTemplate): The prompt template to use

    Returns:
        LLMChain: Initialized LLM chain

    Raises:
        ValueError: If the provider is not supported or configuration is invalid
        Exception: For other initialization errors
    """
    # Log detailed configuration
    config_dict = {
        "provider": config.provider,
        "model": config.model,
        "prompt_type": config.prompt_type,
        "schema_type": config.schema_type,
        "regles": config.regles,
        "examples": config.examples,
        "temperature": config.temperature,
        "max_new_tokens": config.max_new_tokens,
    }

    logger.info(
        f"Initializing LLM chain with provider: {config.provider}, "
        f"model: {config.model}"
    )
    logger.debug(f"Full configuration: {json.dumps(config_dict, indent=2)}")
    logger.debug(f"Using prompt template of type: {config.prompt_type}")

    try:
        if config.provider == "openai":
            model_string = f"openai:{config.model}"
            if config.model == "o4-mini-2025-04-16":
                llm = init_chat_model(model_string)
                logger.info(
                    f"Initialized OpenAI model: {config.model} "
                    f"with temperature {config.temperature}"
                )
            else:
                llm = init_chat_model(model_string, temperature=config.temperature)
                logger.info(
                    f"Initialized OpenAI model: {config.model} "
                    f"with temperature {config.temperature}"
                )

        elif config.provider == "google":
            model_string = f"google_vertexai:{config.model}"
            llm = init_chat_model(model_string, temperature=config.temperature)
            logger.info(
                f"Initialized Google model: {config.model} "
                f"with temperature {config.temperature}"
            )

        elif config.provider == "anthropic":
            model_string = f"anthropic:{config.model}"
            llm = init_chat_model(model_string, temperature=config.temperature)
            logger.info(
                f"Initialized Anthropic model: {config.model} "
                f"with temperature {config.temperature}"
            )

        elif config.provider == "mistralai":
            model_string = f"mistralai:{config.model}"
            llm = init_chat_model(model_string, temperature=config.temperature)
            logger.info(
                f"Initialized Mistralai model: {config.model} "
                f"with temperature {config.temperature}"
            )

        elif config.provider == "huggingface":
            llm = HuggingFaceEndpoint(
                repo_id=config.model,
                max_new_tokens=config.max_new_tokens,
                temperature=config.temperature,
            )
            logger.info(
                f"Initialized Hugging Face model: {config.model} "
                f"with temperature {config.temperature} "
                f"and max_new_tokens {config.max_new_tokens}"
            )
        else:
            raise ValueError(f"Unsupported provider: {config.provider}")

        logger.debug("Successfully initialized LLM chain")
        return LLMChain(llm=llm, prompt=langchain_prompt)
        return LLMChain(llm=llm, prompt=langchain_prompt)

    except Exception as e:
        logger.error(f"Error initializing LLM chain: {e!s}")
        raise

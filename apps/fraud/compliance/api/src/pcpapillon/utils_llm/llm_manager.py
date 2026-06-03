"""
LLM initialization and management.
"""

import json

from langchain.chat_models import init_chat_model
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable
from loguru import logger

from pcpapillon.utils.env_vars import GCP_LOCATION
from pcpapillon.utils_llm.models import LLMConfig


def get_llm_chain(config: LLMConfig, langchain_prompt: ChatPromptTemplate) -> Runnable:
    """
    Create an LLMChain from the provided configuration and prompt.

    Args:
        config (LLMConfig): Configuration for the LLM
        langchain_prompt (ChatPromptTemplate): The prompt template to use

    Returns:
        Runnable: Initialized LLM chain using LCEL pattern

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
        if config.provider == "google":
            model_string = f"google_vertexai:{config.model}"
            llm = init_chat_model(
                model_string, temperature=config.temperature, location=GCP_LOCATION
            )
            logger.info(
                f"Initialized Google model: {config.model} "
                f"with temperature {config.temperature} in region {GCP_LOCATION}"
            )

        else:
            raise ValueError(f"Unsupported provider: {config.provider}")

        logger.debug("Successfully initialized LLM chain using LCEL pattern")
        # Use LCEL pattern: prompt | llm
        return langchain_prompt | llm

    except Exception as e:
        logger.error(f"Error initializing LLM chain: {e!s}")
        raise

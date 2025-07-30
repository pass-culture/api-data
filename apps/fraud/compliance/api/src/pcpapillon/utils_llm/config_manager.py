"""
Configuration management module for LLM framework.
"""

# from configs.default_configs import DEFAULT_CONFIGS
from configs.llm_configs import LLM_CONFIGS
from configs.web_search_configs import WEB_SEARCH_CONFIGS
from loguru import logger
from models import LLMConfig
from schemas.compliance_schemas import COMPLIANCE_SCHEMAS


class ConfigurationManager:
    """Manages LLM configurations and response schemas."""

    def __init__(self):
        self._configs = {}
        self._schemas = {}
        self._register_default_configs()
        self._register_default_schemas()

    def _register_default_configs(self):
        """Register default configurations from external file."""
        # Register LLM configurations
        self._configs.update(LLM_CONFIGS)
        logger.info(f"Registered {len(LLM_CONFIGS)} LLM configurations")

        # Register web search configurations
        self._configs.update(WEB_SEARCH_CONFIGS)
        logger.info(f"Registered {len(WEB_SEARCH_CONFIGS)} web search configurations")

    def _register_default_schemas(self):
        """Register default response schemas from external file."""
        self._schemas.update(COMPLIANCE_SCHEMAS)
        logger.info(f"Registered {len(COMPLIANCE_SCHEMAS)} default schemas")

    def get_config(self, config_name: str) -> LLMConfig:
        """
        Get a configuration by name.

        Args:
            config_name (str): Name of the configuration to retrieve

        Returns:
            LLMConfig: The requested configuration

        Raises:
            KeyError: If the configuration doesn't exist
        """
        if config_name not in self._configs:
            raise KeyError(
                f"""Configuration '{config_name}' not found. Available configurations:
                {list(self._configs.keys())}"""
            )
        return LLMConfig(**self._configs[config_name])

    def get_schema(self, schema_name: str) -> list[dict]:
        """
        Get a response schema by name.

        Args:
            schema_name (str): Name of the schema to retrieve

        Returns:
            List[Dict]: The requested schema

        Raises:
            KeyError: If the schema doesn't exist
        """
        if schema_name not in self._schemas:
            raise KeyError(
                f"""Schema '{schema_name}' not found. Available schemas:
                {list(self._schemas.keys())}"""
            )
        return self._schemas[schema_name]

    def register_config(self, name: str, config: dict) -> None:
        """
        Register a new configuration.

        Args:
            name (str): Name for the configuration
            config (Dict): Configuration dictionary

        Raises:
            ValueError: If the configuration is invalid
        """
        try:
            # Validate the configuration
            LLMConfig(**config)
            self._configs[name] = config
            logger.info(f"Registered new configuration: {name}")
        except Exception as e:
            raise ValueError(f"Invalid configuration: {e!s}")  # noqa: B904

    def register_schema(self, name: str, schema: list[dict]) -> None:
        """
        Register a new response schema.

        Args:
            name (str): Name for the schema
            schema (List[Dict]): Schema definition

        Raises:
            ValueError: If the schema is invalid
        """
        # Basic validation of schema structure
        if not isinstance(schema, list):
            raise ValueError("Schema must be a list of dictionaries")

        for field in schema:
            if not all(k in field for k in ["name", "description", "type"]):
                raise ValueError(
                    "Each schema field must have 'name', 'description', and 'type'"
                )

        self._schemas[name] = schema
        logger.info(f"Registered new schema: {name}")

    def list_configs(self) -> list[str]:
        """List all available configurations."""
        return list(self._configs.keys())

    def list_schemas(self) -> list[str]:
        """List all available schemas."""
        return list(self._schemas.keys())


# Create a global configuration manager instance
config_manager = ConfigurationManager()

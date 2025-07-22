"""
Data models for the LLM framework.
"""

from pydantic import BaseModel, Field, validator


class LLMConfig(BaseModel):
    """Configuration model for LLM settings."""

    provider: str = Field(
        ...,
        description="LLM provider (openai, google, anthropic, "
        "mistralai or huggingface)",
    )
    model: str = Field(..., description="Model name/identifier")
    prompt_type: str = Field(
        ...,
        description="""Type of prompt to use (base, rules, web_search,
        test_agent or few_shot)""",
    )
    schema_type: str = Field(..., description="Type of response schema to use")
    regles: str | None = Field(None, description="Name of the rules file")
    examples: str | None = Field(
        None, description="Name of the examples file (required for few_shot)"
    )
    temperature: float = Field(0.3, description="Model temperature")
    max_new_tokens: int = Field(
        500, description="Maximum number of new tokens to generate"
    )
    web_search: bool = Field(
        False,
        description="Whether to enable web search capabilities",
    )
    # web_search_template: str | None = Field(
    #     None,
    #     description="Template for web search queries (if enabled)",
    # )
    reference_sites: str | None = Field(
        None,
        description="List of reference sites for web search (if enabled)",
    )

    @validator("provider")
    def validate_provider(cls, v):
        if v not in ["openai", "google", "anthropic", "mistralai", "huggingface"]:
            raise ValueError("Provider must be one of: openai, google, huggingface")
        return v

    @validator("prompt_type")
    def validate_prompt_type(cls, v):
        if v not in [
            "base",
            "few_shot",
            "rules",
            "test_agent",
            "web_search_prix",
            "metadonnees_livres",
        ]:
            raise ValueError(
                """Prompt type must be one of: base, few_shot, test_agent, rules,
                web_search_prix, metadonnees_livres"""
            )
        return v

    @validator("examples")
    def validate_examples(cls, v, values):
        if values.get("prompt_type") == "few_shot" and not v:
            raise ValueError("Examples file name is required for few_shot prompt type")
        return v

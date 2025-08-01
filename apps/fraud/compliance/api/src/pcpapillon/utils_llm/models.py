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
    temperature: float = Field(0.3, description="Model temperature")
    max_new_tokens: int = Field(
        500, description="Maximum number of new tokens to generate"
    )
    web_search: bool = Field(
        False,
        description="Whether to enable web search capabilities",
    )

    reference_sites: str | None = Field(
        None,
        description="List of reference sites for web search (if enabled)",
    )

    @validator("provider")
    def validate_provider(cls, v):
        if v not in ["openai", "google"]:
            raise ValueError("Provider must be one of: openai, google")
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
                """Prompt type must be one of: base, rules, web_search_prix"""
            )
        return v

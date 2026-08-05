from pydantic import BaseModel, Field, field_validator


class LLMConfig(BaseModel):
    provider: str = Field(..., description="LLM provider (google, openai)")
    model: str = Field(..., description="Model name/identifier")
    prompt_type: str = Field(..., description="Type of prompt to use")
    schema_type: str = Field(..., description="Type of response schema to use")
    temperature: float = Field(0.3, description="Model temperature")
    web_search: bool = Field(False, description="Whether to enable web search")
    reference_sites: str | None = Field(
        None, description="Reference sites for web search"
    )

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        if v not in ("openai", "google"):
            raise ValueError("Provider must be one of: openai, google")
        return v

    @field_validator("prompt_type")
    @classmethod
    def validate_prompt_type(cls, v: str) -> str:
        valid = {
            "base",
            "few_shot",
            "rules",
            "test_agent",
            "web_search_prix",
            "web_search_book",
            "metadonnees_livres",
        }
        if v not in valid:
            raise ValueError(f"Prompt type must be one of: {valid}")
        return v

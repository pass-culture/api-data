"""LLM configurations."""

LLM_CONFIGS = {
    "Gemini2flash_compliance_validation_instruments": {
        "provider": "google",
        "model": "gemini-2.0-flash-001",
        "prompt_type": "base",
        "schema_type": "compliance_validation",
        "temperature": 0.3,
        "max_new_tokens": 500,
    },
}

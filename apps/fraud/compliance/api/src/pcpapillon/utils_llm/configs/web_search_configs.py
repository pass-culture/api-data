"""Web search configurations."""

WEB_SEARCH_CONFIGS = {
    "config_web_search_check_prix": {
        "provider": "google",
        "model": "gemini-2.5-flash-lite",
        "prompt_type": "web_search_prix",
        "web_search": True,
        "schema_type": "verification_prix_participation",
        "reference_sites": "Woodbrass, Thomann, SonoVente, Star's Music,zambraguitars.com",
    },
}

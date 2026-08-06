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
    "config_web_search_check_livre": {
        "provider": "google",
        "model": "gemini-2.5-flash-lite",
        "prompt_type": "web_search_book",
        "web_search": True,
        "schema_type": "verification_livre",
        "reference_sites": "fnac.com, amazon.fr, leslibraires.fr, babelio.com, thestorygraph.com, doesthedogdie.com, booktriggerwarnings.com, LégiFrance / Journal Officiel, PEN America / ALA (ala.org), The Marshall Project (themarshallproject.org)",
    },
}

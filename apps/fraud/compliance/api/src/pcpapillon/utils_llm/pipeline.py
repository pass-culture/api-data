"""
Compliance validation pipeline: call LLM → parse JSON → optional web search → return result.
"""

import json
import re
from pathlib import Path

from langchain.chat_models import init_chat_model
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from loguru import logger

from pcpapillon.utils.env_vars import GCP_LOCATION
from pcpapillon.utils_llm.configs.llm_configs import LLM_CONFIGS
from pcpapillon.utils_llm.configs.web_search_configs import WEB_SEARCH_CONFIGS
from pcpapillon.utils_llm.models import LLMConfig
from pcpapillon.utils_llm.rules.subcategory_rules_mapping import (
    SUBCATEGORY_RULES_MAPPING,
)
from pcpapillon.utils_llm.schemas.compliance_schemas import COMPLIANCE_SCHEMAS

_RULES_DIR = Path(__file__).parent / "rules"
_PROMPT_DIR = Path(__file__).parent / "prompt"


# ── Config helpers ─────────────────────────────────────────────────────────────


def _get_config(name: str) -> LLMConfig:
    all_configs = {**LLM_CONFIGS, **WEB_SEARCH_CONFIGS}
    if name not in all_configs:
        raise KeyError(f"Config '{name}' not found. Available: {list(all_configs)}")
    return LLMConfig(**all_configs[name])


def _get_schema(schema_type: str) -> list[dict]:
    if schema_type not in COMPLIANCE_SCHEMAS:
        raise KeyError(f"Schema '{schema_type}' not found.")
    return COMPLIANCE_SCHEMAS[schema_type]


# ── File helpers ───────────────────────────────────────────────────────────────


def _read_txt(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    return path.read_text(encoding="utf-8").strip()


def _get_rules(subcategory_id: str) -> str:
    rules_file = SUBCATEGORY_RULES_MAPPING.get(subcategory_id)
    if not rules_file:
        return ""
    return _read_txt(_RULES_DIR / f"{rules_file}.txt")


# ── Format instructions ────────────────────────────────────────────────────────


def _format_instructions(schema: list[dict]) -> str:
    fields = ",\n".join(
        f'  "{s["name"]}": <{s.get("type", "string")}> - {s.get("description", "")}'
        for s in schema
    )
    return (
        "Respond with a valid JSON object:\n{\n"
        + fields
        + "\n}\nIMPORTANT: Respond ONLY with the JSON object, no additional text."
    )


# ── JSON parsing ───────────────────────────────────────────────────────────────


def _parse_json(raw: str, schema: list[dict]) -> dict:
    # Strip markdown code fences if present
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned.strip())

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

    # Bare decision word fallback (e.g. LLM returns just "APPROVED")
    bare = cleaned.strip().lower()
    if bare in ("approved", "rejected", "undetermined"):
        logger.warning(
            f"LLM returned bare decision word: {cleaned!r} — wrapping as reponse_LLM"
        )
        return {
            "reponse_LLM": bare,
            **{s["name"]: None for s in schema if s["name"] != "reponse_LLM"},
        }

    logger.warning(f"Could not parse LLM JSON response: {raw[:300]}")
    return {s["name"]: None for s in schema}


# ── Chain builders ─────────────────────────────────────────────────────────────


def _build_compliance_chain(config: LLMConfig):
    llm = init_chat_model(
        f"google_vertexai:{config.model}",
        temperature=config.temperature,
        location=GCP_LOCATION,
    )
    prompt = ChatPromptTemplate.from_template(
        _read_txt(_PROMPT_DIR / f"{config.prompt_type}.txt")
        + """
        <rules>{regles_conformite}</rules>
        <offer>{offre_commerciale}</offer>
        <instructions>Analyse l'offre commerciale selon les règles de conformité et réponds au format :</instructions>
        <format>{format_instructions}</format>
        """
    )
    return prompt | llm | StrOutputParser()


def _build_web_search_chain(config: LLMConfig):
    llm = init_chat_model(
        f"google_vertexai:{config.model}",
        location=GCP_LOCATION,
        web_search_options={
            "user_location": {
                "type": "approximate",
                "approximate": {"country": "FR", "city": "Paris", "region": "Paris"},
            }
        },
    )
    prompt = ChatPromptTemplate.from_template(
        _read_txt(_PROMPT_DIR / f"{config.prompt_type}.txt")
        + """
        <product>{offer_name}</product>
        <reference_sites>{reference_sites}</reference_sites>
        <comparison_price>{comparison_price}</comparison_price>
        <instructions>Réponds au format :</instructions>
        <format>{format_instructions}</format>
        """
    )
    return prompt | llm | StrOutputParser()


# ── Price validation ───────────────────────────────────────────────────────────


def _invoke_web_search(
    config: LLMConfig, schema: list[dict], offer: dict, comparison_price: float = None
) -> dict:
    chain = _build_web_search_chain(config)
    raw = chain.invoke(
        {
            "offer_name": offer.get("offer_name"),
            "reference_sites": config.reference_sites,
            "comparison_price": comparison_price,
            "format_instructions": _format_instructions(schema),
        }
    )
    return _parse_json(raw, schema)


def _validate_price(
    offer_price: float,
    market_price: float,
    threshold: float,
    llm_explanation: str,
) -> tuple[str, str]:
    if market_price == 0:
        return "rejected", "Prix introuvable sur le web ou produit inexistant."
    divergence = abs((offer_price - market_price) / market_price) * 100
    if divergence > threshold and offer_price > market_price:
        return (
            "rejected",
            f"Prix surévalué de {divergence:.1f}% par rapport au marché (seuil: {threshold}%). Prix moyen: {market_price}€.",
        )
    detail = (
        "Prix inférieur au marché."
        if market_price > offer_price
        else f"Prix cohérent avec le marché (divergence: {divergence:.1f}%)."
    )
    return "approved", f"{llm_explanation}. {detail}"


def _validate_book_result(ws_result: dict, llm_explanation: str) -> tuple[str, str]:
    eligibility = (ws_result.get("eligibilite") or "").strip().lower()
    if eligibility == "non-éligible":
        reason = ws_result.get(
            "raison_ineligibilite", "Contenu non conforme détecté par recherche web."
        )
        return "rejected", reason
    if eligibility == "éligible":
        detail = ws_result.get("explication_recherche", "")
        return "approved", f"{llm_explanation}. {detail}"
    # Unknown eligibility value → fail-safe: reject
    return "rejected", llm_explanation


# ── Main pipeline ──────────────────────────────────────────────────────────────


def run_validation_pipeline(global_config: dict, offer: dict) -> dict:
    """
    Run compliance validation for a single offer.

    Steps:
      1. Call LLM with compliance rules → parse JSON response
      2. If mode is "sequential_pipeline" and LLM approved → web search price check

    Returns:
        dict with keys: validation_status_prediction, validation_status_prediction_reason
    """
    validation_cfg = global_config["validation"]
    mode = validation_cfg.get("mode", "llm_only")
    offer_id = offer.get("offer_id")
    subcategory = offer.get("offer_subcategory_id")
    logger.info(
        f"[{offer_id}] Starting pipeline | mode={mode} | subcategory={subcategory}"
    )

    # Step 1: LLM compliance check
    llm_config = _get_config(validation_cfg["llm_config"])
    schema = _get_schema(llm_config.schema_type)
    logger.info(f"[{offer_id}] Step 1: LLM compliance check | model={llm_config.model}")

    chain = _build_compliance_chain(llm_config)
    raw = chain.invoke(
        {
            "regles_conformite": _get_rules(offer.get("offer_subcategory_id", "")),
            "offre_commerciale": {
                k: offer.get(k)
                for k in (
                    "offer_id",
                    "offer_name",
                    "offer_description",
                    "stock_price",
                    "offer_subcategory_id",
                    "author",
                    "performer",
                )
            },
            "format_instructions": _format_instructions(schema),
        }
    )
    result = _parse_json(raw, schema)
    llm_decision = (result.get("reponse_LLM") or "undetermined").lower()
    llm_explanation = result.get("explication_classification") or ""
    logger.info(f"[{offer_id}] Step 1 done | decision={llm_decision}")

    # Step 2: Optional web search
    if mode == "sequential_pipeline" and llm_decision.lower() in (
        "approved",
        "accepted",
    ):
        price_col = global_config["columns"]["price_to_check"]
        comparison_price = result.get(price_col) or offer.get("stock_price")
        threshold = validation_cfg.get("price_divergence_threshold", 20.0)

        if offer.get("offer_subcategory_id") == "LIVRE_PAPIER":
            logger.info(f"[{offer_id}] Step 2: Book content web search")
            ws_config = _get_config(validation_cfg["book_web_search_config"])
            ws_schema = _get_schema(ws_config.schema_type)
            ws_result = _invoke_web_search(ws_config, ws_schema, offer)
            logger.info(
                f"[{offer_id}] Step 2 done | eligibilite={ws_result.get('eligibilite')}"
            )
            decision, explanation = _validate_book_result(ws_result, llm_explanation)
        else:
            logger.info(
                f"[{offer_id}] Step 2: Price web search | comparison_price={comparison_price}"
            )
            ws_config = _get_config(validation_cfg["web_search_config"])
            ws_schema = _get_schema(ws_config.schema_type)
            ws_result = _invoke_web_search(
                ws_config, ws_schema, offer, comparison_price
            )
            market_price = float(ws_result.get("prix_moyen") or 0)
            offer_price = float(comparison_price or 0)
            logger.info(
                f"[{offer_id}] Step 2 done | market_price={market_price} | offer_price={offer_price}"
            )
            decision, explanation = _validate_price(
                offer_price, market_price, threshold, llm_explanation
            )
    else:
        decision = llm_decision
        explanation = llm_explanation

    # Normalise: anything that is not explicitly "approved" is treated as "rejected"
    # to avoid Pydantic validation errors and ensure fail-safe behaviour.
    if decision not in ("approved", "rejected"):
        logger.warning(
            f"[{offer_id}] Unexpected decision value {decision!r} — defaulting to 'rejected'"
        )
        decision = "rejected"

    logger.info(f"[{offer_id}] Pipeline done | final_decision={decision}")
    return {
        "validation_status_prediction": decision,
        "validation_status_prediction_reason": explanation,
    }

"""
Logic to render recommendation cards visually in the application using Jinja2 templates.
"""

from pathlib import Path

from jinja2 import Environment
from jinja2 import FileSystemLoader
from services.backend_api_client import fetch_offer_details

import streamlit as st
from core.retrieval import calculate_haversine_distance_in_meters


# Jinja2 Setup
TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))


def show_recommendations(
    offer_ids: list, max_offers_to_fetch: int, latitude: float | None, longitude: float | None, title: str
):
    """
    Renders the retrieved offers dynamically directly onto the Streamlit UI.

    Parameters:
    - offer_ids (list): Set of offer UUIDs previously retrieved.
    - max_offers_to_fetch (int): Limit threshold constraint.
    - latitude (float, optional)
    - longitude (float, optional)
    - title (str): Title string for the subheader.
    """
    fetched_offers = []
    offers_to_fetch = offer_ids[:max_offers_to_fetch]
    total_to_fetch = len(offers_to_fetch)

    # Initialize placeholders allowing updates throughout fetching sequence
    progress_bar = st.progress(0, text=f"Chargement des données du backend (0/{total_to_fetch})...")
    alerts_placeholder = st.empty()
    subheader_placeholder = st.empty()
    carousel_placeholder = st.empty()

    # Distances validation constraints tracking
    out_of_bounds_strict_count = 0
    has_strict_offers = False

    STRICT_50KM_SUBCATEGORIES = {
        "ACHAT_INSTRUMENT",
        "JEU_SUPPORT_PHYSIQUE",
        "LIVRE_AUDIO_PHYSIQUE",
        "LIVRE_PAPIER",
        "LOCATION_INSTRUMENT",
        "MATERIEL_ART_CREATIF",
        "PARTITION",
        "SUPPORT_PHYSIQUE_FILM",
        "SUPPORT_PHYSIQUE_MUSIQUE_CD",
        "SUPPORT_PHYSIQUE_MUSIQUE_VINYLE",
    }

    # Fetch CSS securely once via local templates
    template_style = env.get_template("style.css")
    style_content = template_style.render()

    template_html = env.get_template("offer_card.html")
    cards_html_list = []

    # Iterative backend retrieval appending payload contexts sequentially
    for idx, offer_id in enumerate(offers_to_fetch):
        # Extract ID appropriately based on payload structure
        oid = offer_id if isinstance(offer_id, str) else offer_id.get("offer_id", str(offer_id))

        offer_payload = fetch_offer_details(oid)

        progress_bar.progress(
            (idx + 1) / total_to_fetch, text=f"Chargement des données du backend ({idx + 1}/{total_to_fetch})..."
        )

        if offer_payload:
            fetched_offers.append(offer_payload)

            # 1. Verification Logic
            offer_payload = _evaluate_geolocation_constraints(
                offer_payload, latitude, longitude, STRICT_50KM_SUBCATEGORIES
            )

            if offer_payload.get("_distance_violation"):
                out_of_bounds_strict_count += 1
            if str(offer_payload.get("subcategoryId", "")).upper() in STRICT_50KM_SUBCATEGORIES:
                has_strict_offers = True

            # 2. Variable formatting for Jinja injection
            context = _build_jinja_render_context(offer_payload, rank_index=idx)

            # Render individual card
            card_html = template_html.render(context)

            # Inject animation behavior strictly for the last generated component chunk
            is_last = idx == len(offers_to_fetch) - 1
            wrapper_class = "offer-card animate-new" if is_last else "offer-card"

            cards_html_list.append(f'<div class="{wrapper_class}">{card_html}</div>')

            # 3. Progressive Render Refreshes
            subheader_placeholder.subheader(f"📚 {title} ({len(fetched_offers)}/{total_to_fetch} chargées)")

            if has_strict_offers:
                if out_of_bounds_strict_count == 0:
                    alerts_placeholder.success(
                        "✅ Toutes les offres concernées par une limite stricte de distance la respectent bien"
                        "(<= 50km)."
                    )
                else:
                    alerts_placeholder.error(
                        f"⚠️ {out_of_bounds_strict_count} offre(s) concernée(s) par la limite stricte de 50km"
                        "dépasse(nt) la distance !"
                    )

            # Join elements and render
            rendered_cards_stream = "".join(cards_html_list)
            full_html = f"<style>{style_content}</style>\n<div class='carousel-wrapper'>{rendered_cards_stream}</div>"

            if hasattr(st, "html"):
                carousel_placeholder.html(full_html)
            else:
                carousel_placeholder.markdown(full_html.replace("            <", "<"), unsafe_allow_html=True)

    progress_bar.empty()
    subheader_placeholder.subheader(f"📚 {title} ({len(fetched_offers)} offres)")


def show_similar_offer_source(offer_id: str, title: str):
    """
    Renders a single offer card seamlessly onto the Streamlit UI.
    Optimized for displaying single items without recommendation overhead
    (no progress bar, no loading counts, no distance constraints tracking).

    Parameters:
    - offer_id (str): The offer ID to display.
    - title (str): Title string for the subheader.
    """
    offer_payload = fetch_offer_details(offer_id)
    if not offer_payload:
        st.warning("Impossible de récupérer les détails de cette offre.")
        return

    template_style = env.get_template("style.css")
    style_content = template_style.render()
    template_html = env.get_template("offer_card.html")

    # Format simple Jinja injection dict
    context = _build_jinja_render_context(offer_payload, rank_index=0)
    card_html = template_html.render(context)

    # Render simple HTML overlay without carousel constraints loop logic
    full_html = (
        f"<style>{style_content}</style>\n<div class='carousel-wrapper'><div class='offer-card'>{card_html}</div></div>"
    )

    st.subheader(f"📚 {title}")
    if hasattr(st, "html"):
        st.html(full_html)
    else:
        st.markdown(full_html.replace("            <", "<"), unsafe_allow_html=True)


def _evaluate_geolocation_constraints(
    offer: dict, lat: float | None, lon: float | None, strict_categories: set
) -> dict:
    """Computes distance limits silently matching previous monolith structure requirements."""
    MAX_DISTANCE_KM = 50
    if lat is None or lon is None or offer.get("isDigital") is True:
        return offer

    venue_coords = offer.get("venue", {}).get("coordinates", {})
    address_coords = offer.get("address", {}).get("coordinates", {})

    target_lat = venue_coords.get("latitude") or address_coords.get("latitude") or offer.get("latitude")
    target_lon = venue_coords.get("longitude") or address_coords.get("longitude") or offer.get("longitude")

    if target_lat is not None and target_lon is not None:
        try:
            dist_meters = calculate_haversine_distance_in_meters(lat, lon, float(target_lat), float(target_lon))
            if dist_meters is not None:
                dist = dist_meters / 1000.0
                offer["_computed_distance"] = dist

                subcategory_id = str(offer.get("subcategoryId", "")).upper()
                if subcategory_id in strict_categories:
                    if dist > MAX_DISTANCE_KM:
                        offer["_distance_violation"] = True
                elif dist > MAX_DISTANCE_KM:
                    offer["_distance_allowed"] = True
        except (ValueError, TypeError):
            pass

    return offer


def _build_jinja_render_context(offer: dict, rank_index: int) -> dict:
    """Prepares formatted visual data dictionaries to feed into Jinja rendering."""
    THOUSAND_LIKES_THRESHOLD = 1000
    MAX_DESCRIPTION_LENGTH = 60
    title = offer.get("name", "Titre inconnu")
    offer_id_val = offer.get("id", "N/A")
    raw_desc = offer.get("description") or ""

    category = str(offer.get("subcategoryId", "LIVRES")).capitalize()

    images = offer.get("images", {})
    image_url = (
        images.get("recto", {}).get("url") if images else "https://via.placeholder.com/300x450?text=Image+Indisponible"
    )

    rank_number = rank_index + 1
    likes_count = 620 + (rank_index * 315)
    likes_text = (
        f"{likes_count / THOUSAND_LIKES_THRESHOLD:.1f}k j'aime".replace(".", ",")
        if likes_count > THOUSAND_LIKES_THRESHOLD
        else f"{likes_count} j'aime"
    )

    # Handle formatting description strings preventing HTML attacks
    safe_desc = raw_desc.replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    short_desc = safe_desc[:MAX_DESCRIPTION_LENGTH] if len(safe_desc) > MAX_DESCRIPTION_LENGTH else safe_desc
    has_ellipsis = len(safe_desc) > MAX_DESCRIPTION_LENGTH

    dist = offer.get("_computed_distance")
    dist_details = {
        "value": dist,
        "violation": offer.get("_distance_violation"),
        "allowed": offer.get("_distance_allowed"),
    }

    metadata = offer.get("metadata", {})
    low_price = metadata.get("offers", {}).get("lowPrice")
    price_text = f"Dès {str(low_price).replace('.', ',')} €" if low_price else "Prix non renseigné"

    return {
        "rank_number": rank_number,
        "image_url": image_url,
        "likes_text": likes_text,
        "category": category,
        "title": title,
        "price": price_text,
        "dist": dist_details,
        "offer_url": f"https://app.staging.passculture.team/offre/{offer_id_val}",
        "offer_id": offer_id_val,
        "safe_desc": safe_desc,
        "short_desc": short_desc,
        "has_ellipsis": has_ellipsis,
    }

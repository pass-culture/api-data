"""
Request Debug Component.

Displays an expandable panel after each API call, showing the full details
of the HTTP request that was sent:
  - HTTP method badge (color-coded)
  - Full URL with query string (token masked)
  - Query parameters as JSON
  - Request body / payload as JSON (for POST requests)
  - Proxy configuration if any
"""

import streamlit as st


def _build_display_url(url: str, query_params: dict) -> str:
    """Build a displayable URL with the query string appended.

    The API token is excluded from the URL to avoid exposing it.

    Args:
        url: Base endpoint URL.
        query_params: Dict of query parameters (already filtered, non-None values only).

    Returns:
        The URL with the query string appended, or the bare URL if no params.
    """
    visible_params = {k: v for k, v in query_params.items() if k != "token"}

    if not visible_params:
        return url

    parts = []
    for key, value in visible_params.items():
        if isinstance(value, list):
            parts.extend(f"{key}={item}" for item in value)
        else:
            parts.append(f"{key}={value}")

    query_string = "&".join(parts)
    return f"{url}?{query_string}"


def render_request_debug(
    method: str,
    url: str,
    query_params: dict | None = None,
    body: dict | None = None,
    proxies: dict | None = None,
) -> None:
    """Render an expandable panel showing the full details of an API request.

    Args:
        method: HTTP method (e.g. "GET", "POST").
        url: Full endpoint URL, without query string.
        query_params: URL query parameters. The "token" key is masked in the display.
        body: JSON request body (used for POST requests).
        proxies: Optional proxy configuration dict (keys: "http", "https").
    """
    clean_query_params = {k: v for k, v in (query_params or {}).items() if v is not None}
    clean_body = {k: v for k, v in (body or {}).items() if v is not None}

    display_url = _build_display_url(url, clean_query_params)

    with st.expander("🔍 Request details", expanded=False):
        # --- Method badge + URL ---
        col_method, col_url = st.columns([1, 5])
        with col_method:
            badge_color = "#2196f3" if method == "GET" else "#4caf50"
            st.markdown(
                f'<span style="background:{badge_color}; color:white; font-weight:700;'
                f' padding:3px 10px; border-radius:4px; font-size:13px;">{method}</span>',
                unsafe_allow_html=True,
            )
        with col_url:
            st.code(display_url, language=None)

        # --- Query parameters ---
        if clean_query_params:
            st.markdown("**Query parameters**")
            masked_params = {k: ("***" if k == "token" else v) for k, v in clean_query_params.items()}
            st.json(masked_params)

        # --- Request body ---
        if clean_body:
            st.markdown("**Request body (payload)**")
            st.json(clean_body)

        # --- Proxy ---
        if proxies:
            st.markdown("**Proxy**")
            st.code(proxies.get("https") or proxies.get("http", ""), language=None)

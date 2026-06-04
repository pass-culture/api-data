"""
Environment Banner Component.

Displays a compact, color-coded banner at the top of each Streamlit page
to clearly indicate which API environment is currently targeted
(local, dev, staging, prod).

The environment is detected in two steps:
  1. By inspecting the API URL (e.g. "stg" in the URL → staging).
  2. As a fallback, by reading the DEPLOY_ENV environment variable set by the Makefile.
"""

import os

import streamlit as st


_LOCAL_HOST_PATTERNS = ("localhost", "127.0.0.", "0.0.0.0")

_ENV_CONFIG = {
    "local": {
        "label": "LOCAL",
        "emoji": "🖥️",
        "bg": "#e8f5e9",
        "border": "#4caf50",
        "text": "#1b5e20",
        "badge_bg": "#4caf50",
    },
    "dev": {
        "label": "DEV",
        "emoji": "🔧",
        "bg": "#e3f2fd",
        "border": "#2196f3",
        "text": "#0d47a1",
        "badge_bg": "#2196f3",
    },
    "staging": {
        "label": "STAGING",
        "emoji": "🧪",
        "bg": "#fff8e1",
        "border": "#ff9800",
        "text": "#e65100",
        "badge_bg": "#ff9800",
    },
    "prod": {
        "label": "PRODUCTION",
        "emoji": "🚨",
        "bg": "#ffebee",
        "border": "#f44336",
        "text": "#b71c1c",
        "badge_bg": "#f44336",
    },
}


def _detect_env(api_url: str) -> str:
    """Detect the target environment from the API URL, falling back to DEPLOY_ENV.

    Detection priority:
      1. Localhost patterns → "local"
      2. Keywords in the API URL (prod / stg / staging / dev)
      3. DEPLOY_ENV environment variable set by the Makefile

    Args:
        api_url: The API base URL currently in use.

    Returns:
        One of: "local", "dev", "staging", "prod".
    """
    url_lower = api_url.lower()
    deploy_env = os.environ.get("DEPLOY_ENV", "").lower()

    if any(pattern in url_lower for pattern in _LOCAL_HOST_PATTERNS):
        return "local"

    env = "local"

    if "prod" in url_lower:
        env = "prod"
    elif "stg" in url_lower or "staging" in url_lower:
        env = "staging"
    elif "dev" in url_lower:
        env = "dev"
    elif deploy_env in ("prod", "production"):
        env = "prod"
    elif deploy_env in ("stg", "staging"):
        env = "staging"
    elif deploy_env == "dev":
        env = "dev"

    return env


def render_env_banner(api_url: str) -> None:
    """Render a compact, color-coded banner showing the current API environment and URL.

    The banner displays, on a single line:
      - An environment badge (e.g. STAGING) with a matching background color
      - The full API URL

    Args:
        api_url: The API base URL currently in use.
    """
    env_key = _detect_env(api_url)
    cfg = _ENV_CONFIG[env_key]

    st.markdown(
        f"""
        <div style="
            background-color: {cfg["bg"]};
            border-left: 4px solid {cfg["border"]};
            border-radius: 6px;
            padding: 7px 14px;
            margin-bottom: 14px;
            display: flex;
            align-items: center;
            gap: 10px;
        ">
            <span style="font-size: 16px;">{cfg["emoji"]}</span>
            <span style="
                background-color: {cfg["badge_bg"]};
                color: white;
                font-weight: 700;
                font-size: 12px;
                padding: 2px 8px;
                border-radius: 12px;
                letter-spacing: 0.5px;
            ">{cfg["label"]}</span>
            <span style="font-size: 12px; color: {cfg["text"]}; word-break: break-all;">
                🌐 <b>{api_url}</b>
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )

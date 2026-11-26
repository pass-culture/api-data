"""
Main entry point for the Streamlit Recommendation Application.

Routes between the home page and one page per Recommendation API V2 endpoint
(see `endpoint_pages.py`).
"""

from endpoint_pages import ENDPOINT_PAGES
from endpoint_pages import HOME_PAGE_PATH

import streamlit as st


def main():
    home_page = st.Page(HOME_PAGE_PATH, title="Accueil", icon="🏠", default=True)
    endpoint_pages = [st.Page(page.path, title=page.title, icon=page.icon) for page in ENDPOINT_PAGES]

    st.navigation({"": [home_page], "Endpoints": endpoint_pages}).run()


if __name__ == "__main__":
    main()

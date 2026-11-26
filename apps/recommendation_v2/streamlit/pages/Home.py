"""
Home Page of the Streamlit Recommendation Application.

Lists every endpoint of the Recommendation API V2 and links to its dedicated page.
"""

from endpoint_pages import ENDPOINT_PAGES

import streamlit as st


CARDS_PER_ROW = 3

TILES_STYLE = """
<style>
.st-key-endpoint-tiles [data-testid="stPageLink-NavLink"] {
    min-height: 140px;
    padding: 20px 24px;
    border: 1px solid rgba(128, 128, 128, 0.3);
    border-radius: 12px;
    align-items: flex-start;
    transition: border-color 0.15s, box-shadow 0.15s;
}
.st-key-endpoint-tiles [data-testid="stPageLink-NavLink"]:hover {
    border-color: #ff4b4b;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}
.st-key-endpoint-tiles [data-testid="stPageLink-NavLink"] p {
    font-size: 1rem;
    line-height: 1.8;
}
</style>
"""


def main():
    st.set_page_config(page_title="API de Recommandation V2", layout="wide")

    st.title("✨ Proxy de l'API de Recommandation V2")
    st.markdown("Choisissez l'endpoint à tester.")

    st.markdown(TILES_STYLE, unsafe_allow_html=True)

    with st.container(key="endpoint-tiles", gap="large"):
        for row_start in range(0, len(ENDPOINT_PAGES), CARDS_PER_ROW):
            columns = st.columns(CARDS_PER_ROW, gap="large")
            for column, page in zip(columns, ENDPOINT_PAGES[row_start : row_start + CARDS_PER_ROW], strict=False):
                with column:
                    st.page_link(
                        page.path,
                        label=f"**{page.title}**  \n`{page.method} {page.endpoint}`  \n{page.description}",
                        icon=page.icon,
                        width="stretch",
                    )


if __name__ == "__main__":
    main()

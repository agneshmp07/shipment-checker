"""The small Guide button under each page title: the page's three steps open in a pop-up (ui/guide.py)."""
import streamlit as st

from ui.guide import page_guide

TITLES = {"chat": "Booking by chat or voice", "upload": "Checking a bookings file", "market": "The Marketplace"}


def how_to(page_key: str, items: list[tuple[str, str]]):
    """A Guide button instead of a 'How to use this page' box filling the page."""
    if st.button("Guide", key=f"guide-{page_key}", icon=":material/menu_book:", type="tertiary",
                 help="How this page works, in three steps"):
        page_guide(TITLES.get(page_key, "How this page works"), items)

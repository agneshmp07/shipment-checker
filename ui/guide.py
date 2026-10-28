"""The Guide: everything a first-time user needs, in one pop-up, so the pages themselves stay short.

`app_guide()` is the full guide (Home's Guide button): quick start, the sections, the 10 rules and key terms.
`page_guide()` is one page's three steps (opened by ui/guide_button.py's Guide button)."""
from __future__ import annotations

import streamlit as st

from ui.brand import steps

QUICK_START = [
    ("Tell us", "Type or speak your shipment in plain English, or upload your Bookings and Items sheets. "
                "We only ask for what's missing."),
    ("We check", "10 rules catch the mistakes that cause customs holds and 'missing' cartons. Every problem "
                 "shows the real numbers, why it matters and how to fix it."),
    ("You ship", "Once the pre-flight check clears, get the best carrier, the confirmation, carton labels "
                 "and the commercial invoice."),
]
SECTIONS = [
    (":material/chat:", "Book by chat or voice", "Describe your shipment in your own words or tap the mic. "
     "The assistant asks only for what's missing.", "app_pages/chat_booking.py"),
    (":material/fact_check:", "Check a bookings file", "Upload many bookings at once, see which can ship, and "
     "fix the sure mistakes in one tap.", "app_pages/upload_file.py"),
    (":material/smart_toy:", "Ask AI", "The button at the top of every page: “why is BK-107 blocked?”, "
     "“what's an HS code?”.", None),
    (":material/storefront:", "Marketplace", "Coming next: find buyers in the EU and message them. Demo data "
     "for now.", "app_pages/trade_connect.py"),
]
RULES = ("- **Customs paperwork** — HS codes, declared value vs items, country of origin, dangerous goods.\n"
         "- **Counts** — units per carton × cartons = quantity, and booking cartons = item cartons.\n"
         "- **Weights** — weight per pallet within the carrier's limit; gross weight at least the goods.\n"
         "- **Logistics** — a delivery slot at warehouses, and a ready date that isn't in the past.")
TERMS = {
    "Pre-flight check": "The 10 rules run before a shipment leaves. Documents unlock only when it clears.",
    "HS code": "The international code that classifies each product for customs (at least 6 digits).",
    "Declared value": "The total value of the goods as stated on the paperwork.",
    "Commercial invoice": "The document listing what's in the shipment and what it's worth.",
    "Carton / pallet": "A carton is a box of units; a pallet is the platform holding many cartons.",
    "Customs hold": "When customs stops a shipment until its paperwork is fixed.",
    "Delivery appointment": "A booked time slot at the receiving warehouse.",
}


def _go(page: str):
    st.session_state.guide_go = page


@st.dialog("Guide", width="large", icon=":material/menu_book:")
def app_guide():
    quick, sections, rules, terms = st.tabs(["Quick start", "Sections", "The 10 rules", "Key terms"])
    with quick:
        steps(QUICK_START)
    with sections:
        for icon, title, text, page in SECTIONS:
            with st.container(border=True, horizontal=True, vertical_alignment="center"):
                st.markdown(f"**{icon} {title}**  \n{text}")
                if page:
                    st.button("Open", key=f"guide-open-{page}", icon=":material/arrow_forward:",
                              on_click=_go, args=(page,))
    with rules:
        st.markdown(RULES)
        st.caption(":red-badge[Red] must be fixed before shipping · :orange-badge[Amber] a warning to check")
    with terms:
        st.table(TERMS, border="horizontal")


@st.dialog("Guide", width="medium", icon=":material/menu_book:")
def page_guide(title: str, items: list[tuple[str, str]]):
    st.markdown(f"**{title}**")
    steps(items)


def follow():
    """Switch page if a guide's Open button was pressed (call where switch_page is allowed)."""
    page = st.session_state.pop("guide_go", None)
    if page:
        st.switch_page(page)

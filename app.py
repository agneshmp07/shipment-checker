"""Entry point: streamlit run app.py"""
import os

import streamlit as st

from ui.assistant import render_ask_ai

# Streamlit Cloud / HF Spaces secrets -> env vars read by core.llm (never hard-coded).
for name in ("ANTHROPIC_API_KEY", "ANTHROPIC_MODEL", "GEMINI_API_KEY", "GOOGLE_API_KEY", "GEMINI_MODEL"):
    try:
        if name in st.secrets and not os.environ.get(name):
            os.environ[name] = str(st.secrets[name])
    except Exception:  # no secrets file at all: fine, the app runs without the LLM
        pass

st.set_page_config(page_title="ShipCheck — shipment pre-flight checker", page_icon=":material/local_shipping:",
                   layout="wide")
st.logo("assets/logo.svg", size="large")
# Hide the hosting toolbar (Streamlit Cloud's Fork / GitHub buttons and the ⋮ developer menu):
# they're about where the app is hosted, not about ShipCheck.
st.html("<style>[data-testid='stToolbarActions'],[data-testid='stMainMenu']{display:none !important}</style>")

page = st.navigation([
    st.Page("app_pages/home.py", title="Home", icon=":material/home:", default=True),
    st.Page("app_pages/chat_booking.py", title="Book by chat", icon=":material/chat:"),
    st.Page("app_pages/upload_file.py", title="Check a file", icon=":material/fact_check:"),
    st.Page("app_pages/trade_connect.py", title="Marketplace", icon=":material/storefront:"),
], position="top")
st.session_state.current_page = page.title
render_ask_ai(page.title)
page.run()

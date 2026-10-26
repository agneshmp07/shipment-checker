"""Entry point: streamlit run app.py"""
import os

import streamlit as st

from ui.assistant import render_ask_ai
from ui.brand import global_style

# Streamlit Cloud / HF Spaces secrets -> env vars read by core.llm (never hard-coded).
# Tests set OOPS_PROOF_NO_SECRETS so a key in a local secrets.toml is never used by them.
SECRET_NAMES = ("ANTHROPIC_API_KEY", "ANTHROPIC_MODEL", "GEMINI_API_KEY", "GOOGLE_API_KEY", "GEMINI_MODEL")
for name in () if os.environ.get("OOPS_PROOF_NO_SECRETS") else SECRET_NAMES:
    try:
        if name in st.secrets and not os.environ.get(name):
            os.environ[name] = str(st.secrets[name])
    except Exception:  # no secrets file at all: fine, the app runs without the LLM
        pass

st.set_page_config(page_title="Oops-Proof — catch shipment mistakes before customs does", page_icon="assets/favicon.png",
                   layout="wide")
st.logo("assets/logo.svg", size="large")
global_style()        # hides the hosting toolbar, adds hover effects

page = st.navigation([
    st.Page("app_pages/home.py", title="Home", icon=":material/home:", default=True),
    st.Page("app_pages/chat_booking.py", title="Book by chat", icon=":material/chat:"),
    st.Page("app_pages/upload_file.py", title="Check a file", icon=":material/fact_check:"),
    st.Page("app_pages/trade_connect.py", title="Marketplace", icon=":material/storefront:"),
], position="top")
st.session_state.current_page = page.title
render_ask_ai(page.title)
page.run()

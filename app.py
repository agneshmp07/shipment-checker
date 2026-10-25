"""Entry point: streamlit run app.py"""
import os

import streamlit as st

# Streamlit Cloud / HF Spaces secrets -> env vars read by core.llm (never hard-coded).
for name in ("ANTHROPIC_API_KEY", "ANTHROPIC_MODEL", "GEMINI_API_KEY", "GOOGLE_API_KEY", "GEMINI_MODEL"):
    try:
        if name in st.secrets and not os.environ.get(name):
            os.environ[name] = str(st.secrets[name])
    except Exception:  # no secrets file at all: fine, the app runs without the LLM
        pass

st.set_page_config(page_title="Shipment pre-flight checker", page_icon=":material/local_shipping:",
                   layout="wide")

page = st.navigation([
    st.Page("app_pages/home.py", title="Home", icon=":material/home:", default=True),
    st.Page("app_pages/chat_booking.py", title="Book by chat", icon=":material/chat:"),
    st.Page("app_pages/upload_file.py", title="Upload a file", icon=":material/upload_file:"),
    st.Page("app_pages/trade_connect.py", title="Trade Connect", icon=":material/handshake:"),
], position="top")
page.run()

import streamlit as st

from ui import guide
from ui.brand import hero

hero(
    kicker="Pre-flight check · UK → Germany · France · Netherlands",
    title_html="Every shipment has an oops. <span>We catch it before customs does.</span>",
    subtitle="Book by chat, voice or Excel. We check it against 10 customs and warehouse rules, fix the "
             "mistakes and pick the best carrier.",
    chips=["Pre-flight check in seconds", "Plain-English fixes", "Best of 3 carriers", "Voice + AI assistant"],
)

with st.container(horizontal=True):
    if st.button("Book by chat or voice", type="primary", icon=":material/mic:"):
        st.switch_page("app_pages/chat_booking.py")
    if st.button("Check a bookings file", icon=":material/upload_file:"):
        st.switch_page("app_pages/upload_file.py")
    show_guide = st.button("Guide", icon=":material/menu_book:", key="home-guide",
                           help="Quick start, every section, the 10 rules and key terms")
if show_guide:                                 # opened outside the row, so the row isn't drawn twice
    guide.app_guide()
guide.follow()


def _use_example():
    """Send the tapped example to the chat page, and clear the pill for next time."""
    st.session_state.chat_prefill = st.session_state.home_example
    st.session_state.home_example = None
    st.session_state.go_chat = True


st.markdown("#### Try saying one of these")
st.pills(
    "Examples", label_visibility="collapsed", key="home_example", on_change=_use_example,
    options=["I'm sending 1080 mugs from Manchester to a warehouse in Frankfurt",
             "500 cotton t-shirts from London to a shop in Paris, as fast as possible",
             "2,000 notebooks from Birmingham to Amsterdam, cheapest please"])
if st.session_state.pop("go_chat", False):
    st.switch_page("app_pages/chat_booking.py")

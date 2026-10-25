import streamlit as st

from ui.brand import hero, steps

hero(
    kicker="UK → Germany · France · Netherlands",
    title_html="Ship to Europe <span>without surprises</span>",
    subtitle="Tell us about your shipment by chat, voice or Excel. We check it against 10 customs and "
             "warehouse rules, show you exactly how to fix any mistake, and pick the best carrier.",
    chips=["10 checks in seconds", "Plain-English fixes", "Best of 3 carriers", "Voice + AI assistant"],
)

with st.container(horizontal=True):
    if st.button("Book by chat or voice", type="primary", icon=":material/mic:"):
        st.switch_page("app_pages/chat_booking.py")
    if st.button("Check a bookings file", icon=":material/upload_file:"):
        st.switch_page("app_pages/upload_file.py")

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

st.markdown("#### How it works")
steps([
    ("Tell us", "Type or speak your shipment in plain English, or upload your Bookings and Items "
                "sheets. We only ask for what's missing."),
    ("We check", "10 rules catch the mistakes that cause customs holds and 'missing' cartons. Each "
                 "problem shows the real numbers, why it matters and a one-tap fix."),
    ("You ship", "We recommend the best carrier for your priority, explain the trade-off, and give you a "
                 "plain-English confirmation and next steps."),
])

st.markdown("#### Everything in ShipCheck")
cards = [
    (":material/chat:", "Book by chat or voice", "Describe your shipment in your own words or tap the mic. "
     "The assistant asks only for what's missing and updates the checks as you change things.",
     "app_pages/chat_booking.py", "Start a booking"),
    (":material/fact_check:", "Check a bookings file", "Upload many bookings at once. See which are ready, "
     "which need fixing, the most common mistake, and fix them with one tap.",
     "app_pages/upload_file.py", "Upload a file"),
    (":material/storefront:", "Marketplace", "Find buyers in Germany, France and the Netherlands, post your "
     "own listing, see buyers matched to your bookings and message them. Checked sellers get a badge.",
     "app_pages/trade_connect.py", "Open the marketplace"),
    (":material/smart_toy:", "AI assistant", "Stuck? Tap Ask AI at the top of any page: “why is BK-107 "
     "blocked?”, “what's an HS code?”. It answers from your actual results.",
     None, None),
]
cols = st.columns(2)
for n, (icon, title, text, page, link) in enumerate(cards):
    with cols[n % 2], st.container(border=True):
        st.markdown(f"#### {icon} {title}")
        st.write(text)
        if page:
            st.page_link(page, label=link, icon=":material/arrow_forward:")
        else:
            st.caption("Look for the **Ask AI** button at the top of every page.")

with st.expander("What we check (the 10 rules)", icon=":material/rule:"):
    st.markdown(
        "- **Customs paperwork** — HS codes (the international code customs uses to classify a product), "
        "declared value vs items, country of origin, and dangerous goods (lithium batteries, aerosols, "
        "flammable liquids).\n"
        "- **Counts** — units per carton × cartons = quantity, and booking cartons = item cartons, so the "
        "warehouse doesn't report anything missing.\n"
        "- **Weights** — weight per pallet (a pallet is the platform the cartons are stacked on) within the "
        "carrier's limit, and gross weight at least the weight of the goods.\n"
        "- **Logistics** — a delivery slot at warehouses, and a ready date that isn't in the past.")
    st.caption(":red-badge[Red] must be fixed before shipping · :orange-badge[Amber] warning, should be fixed")

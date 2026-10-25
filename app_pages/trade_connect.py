"""Trade Connect (add-on, demo data): find buyers and sellers; pre-checked shippers get a badge."""
from datetime import date, datetime

import streamlit as st

from core.chat_agent import is_complete
from core.check import evaluate
from core.trade_connect import filter_directory, load_directory, prechecked_sellers, validate_request
from ui.results import get_carriers

st.title("Trade Connect")
st.badge("Demo data — sample businesses, not real companies", color="violet", icon=":material/science:")
st.write("Find buyers and sellers across the UK, Germany, France and the Netherlands. Sellers whose "
         "current bookings all pass every check get a **Pre-checked shipper ✅** badge.")

if "connect_requests" not in st.session_state:
    st.session_state.connect_requests = []

# ---- Current bookings -> pre-checked sellers -------------------------------------
carriers, today = get_carriers(), date.today()
current = list(st.session_state.get("upload_bookings") or [])
chat = st.session_state.get("chat")
if chat is not None and is_complete(chat):
    current.append(chat.booking)
evals = [evaluate(b, carriers, today) for b in current]
prechecked = prechecked_sellers(evals)

# ---- Your seller profile preview ------------------------------------------------------
st.subheader("Your seller profile")
sellers: dict[str, list] = {}
for ev in evals:
    if ev.booking.seller_name:
        sellers.setdefault(ev.booking.seller_name.strip(), []).append(ev)
if not sellers:
    st.info("Book a shipment by chat or upload a bookings file, and your profile preview appears here. "
            "Sellers whose bookings are all 🟢 Ready to ship get the Pre-checked shipper badge.",
            icon=":material/person:")
else:
    names = sorted(sellers, key=lambda n: (n.lower() not in prechecked, n.lower()))
    st.caption(f"{sum(n.lower() in prechecked for n in names)} of {len(names)} sellers in your current "
               "bookings are pre-checked.")
    name = st.selectbox("Preview the profile for", names)
    evs = sellers[name]
    ok = name.lower() in prechecked
    with st.container(border=True, width=520):
        st.markdown(f"**{name}** " + (":green-badge[Pre-checked shipper ✅]" if ok else ""))
        routes = sorted({f"{e.booking.origin_city} → {e.booking.destination_city}" for e in evs})
        goods = sorted({it.description for e in evs for it in e.booking.items if it.description})
        st.caption(" · ".join(routes))
        st.write("Ships: " + (", ".join(goods[:5]) or "—"))
        if ok:
            st.caption(f"All {len(evs)} booking(s) pass all 10 checks.")
        else:
            not_ready = [f"{e.booking.booking_id} ({e.badge})" for e in evs if e.status != "Ready"]
            st.caption("Not pre-checked yet: fix " + ", ".join(not_ready) + " to earn the badge.")

# ---- Directory -----------------------------------------------------------------------
st.subheader("Directory")
directory = load_directory()
all_categories = sorted({c for e in directory for c in e.categories})
with st.container(horizontal=True, vertical_alignment="bottom"):
    query = st.text_input("Search", placeholder="Name, city or product", width=260)
    countries = st.multiselect("Country", ["United Kingdom", "Germany", "France", "Netherlands"], width=300)
    role = st.segmented_control("Looking for", ["All", "Buyer", "Seller"], default="All")
    categories = st.multiselect("Category", all_categories, width=300)

results = filter_directory(directory, countries, role, categories, query)
st.caption(f"{len(results)} of {len(directory)} businesses")


@st.dialog("Request to connect")
def connect_dialog(business_name: str):
    st.write(f"Send a connection request to **{business_name}**.")
    with st.form("connect_form", border=False):
        name = st.text_input("Your name")
        email = st.text_input("Your email")
        message = st.text_area("Message", placeholder="Tell them what you sell or buy, and why you'd like to connect.")
        if st.form_submit_button("Send request", type="primary"):
            problems = validate_request(name, email, message)
            for p in problems:
                st.error(p)
            if not problems:
                st.session_state.connect_requests.append({
                    "To": business_name, "From": name.strip(), "Email": email.strip(),
                    "Message": message.strip(), "Sent": datetime.now().strftime("%d-%m-%Y %H:%M")})
                st.session_state.connect_sent = business_name
                st.rerun()


sent = st.session_state.pop("connect_sent", None)
if sent:
    st.success(f"Request sent to {sent}. (Demo: requests are kept in this browser session only.)",
               icon=":material/send:")

cols = st.columns(3)
for n, biz in enumerate(results):
    with cols[n % 3], st.container(border=True):
        badge = " :green-badge[Pre-checked shipper ✅]" if biz.role == "Seller" and biz.name.lower() in prechecked else ""
        st.markdown(f"**{biz.name}**{badge}")
        st.caption(f"{biz.city}, {biz.country} · {biz.role}")
        st.markdown(" ".join(f":gray-badge[{c}]" for c in biz.categories))
        st.write(biz.about)
        if st.button("Request to connect", key=f"connect-{n}", icon=":material/handshake:"):
            connect_dialog(biz.name)
if not results:
    st.info("No businesses match these filters.", icon=":material/search_off:")

if st.session_state.connect_requests:
    with st.expander(f"Your connection requests ({len(st.session_state.connect_requests)})"):
        st.dataframe(st.session_state.connect_requests, hide_index=True)

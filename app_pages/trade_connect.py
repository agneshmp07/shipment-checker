"""Marketplace (demo data): find partners, buyers matched to your bookings, your listing, inbox."""
from datetime import date, datetime

import streamlit as st

from core.chat_agent import is_complete
from core.check import evaluate
from core.trade_connect import (CATEGORIES, Business, Message, Thread, categories_for, demo_reply,
                                filter_directory, load_directory, match_buyers, prechecked_sellers,
                                validate_request)
from ui.brand import how_to, page_title
from ui.results import get_carriers

COUNTRIES = ["United Kingdom", "Germany", "France", "Netherlands"]

page_title("Marketplace", "Find buyers and sellers across the UK, Germany, France and the Netherlands — "
           "and get matched with buyers for the goods you're shipping.")
st.badge("Demo data — sample businesses, not real companies; replies are automatic", color="violet",
         icon=":material/science:")
how_to("market", [
    ("Find partners", "Search and filter businesses by country, buyer or seller, and category."),
    ("See your matches", "After you book or upload, we suggest buyers who want those goods — in your "
                         "destination country first."),
    ("List & message", "Post your own listing, send connection requests and reply in your inbox. Sellers whose "
                       "bookings all pass get a Pre-checked shipper ✅ badge."),
])

st.session_state.setdefault("threads", {})
st.session_state.setdefault("my_listings", [])
threads: dict[str, Thread] = st.session_state.threads

# ---- Current bookings -> pre-checked sellers -------------------------------------------
carriers, today = get_carriers(), date.today()
current = list(st.session_state.get("upload_bookings") or [])
chat = st.session_state.get("chat")
if chat is not None and is_complete(chat):
    current.append(chat.booking)
evals = [evaluate(b, carriers, today) for b in current]
prechecked = prechecked_sellers(evals)
directory = load_directory() + st.session_state.my_listings
mine = {b.name for b in st.session_state.my_listings}


def now() -> str:
    return datetime.now().strftime("%d-%m-%Y %H:%M")


def badge_for(biz: Business) -> str:
    out = ""
    if biz.role == "Seller" and biz.name.lower() in prechecked:
        out += " :green-badge[Pre-checked shipper ✅]"
    if biz.name in mine:
        out += " :orange-badge[Your listing]"
    return out


@st.dialog("Request to connect")
def connect_dialog(business_name: str, suggested: str = ""):
    st.write(f"Send a connection request to **{business_name}**.")
    with st.form("connect_form", border=False):
        name = st.text_input("Your name")
        email = st.text_input("Your email")
        message = st.text_area("Message", value=suggested,
                               placeholder="Tell them what you sell or buy, and why you'd like to connect.")
        if st.form_submit_button("Send request", type="primary"):
            problems = validate_request(name, email, message)
            for p in problems:
                st.error(p)
            if not problems:
                biz = next(b for b in directory if b.name == business_name)
                t = threads.setdefault(business_name, Thread(business=business_name, messages=[]))
                t.messages.append(Message(sender="you", text=message.strip(), sent=now()))
                t.messages.append(Message(sender=business_name, text=demo_reply(biz, message), sent=now()))
                st.session_state.connect_sent = business_name
                st.rerun()


sent = st.session_state.pop("connect_sent", None)
if sent:
    st.success(f"Request sent to {sent} — they replied in your Inbox. (Demo: replies are automatic.)",
               icon=":material/send:")


def biz_card(biz: Business, key: str, reasons: list[str] | None = None, suggested: str = ""):
    with st.container(border=True):
        st.markdown(f"**{biz.name}**{badge_for(biz)}")
        st.caption(f":material/location_on: {biz.city}, {biz.country} · {biz.role}")
        st.markdown(" ".join(f":gray-badge[{c}]" for c in biz.categories))
        st.write(biz.about)
        for r in reasons or []:
            st.caption(f":material/check: {r}")
        if biz.name not in mine:
            label = "Message again" if biz.name in threads else "Request to connect"
            if st.button(label, key=key, icon=":material/handshake:"):
                connect_dialog(biz.name, suggested)


unread = sum(1 for t in threads.values() if t.messages and t.messages[-1].sender != "you")
tab_find, tab_match, tab_list, tab_inbox = st.tabs(
    [":material/travel_explore: Find partners", ":material/join_inner: Matches for my bookings",
     ":material/storefront: My listing", f":material/inbox: Inbox ({unread} new)" if unread else
     ":material/inbox: Inbox"], key="market_tab", on_change="rerun")

# ---- Find partners ------------------------------------------------------------------------
with tab_find:
    with st.container(horizontal=True, vertical_alignment="bottom"):
        query = st.text_input("Search", placeholder="Name, city or product", width=240)
        countries = st.multiselect("Country", COUNTRIES, width=280)
        role = st.segmented_control("Looking for", ["All", "Buyer", "Seller"], default="All")
        categories = st.multiselect("Category", sorted({c for e in directory for c in e.categories}), width=280)
    results = filter_directory(directory, countries, role, categories, query)
    st.caption(f"{len(results)} of {len(directory)} businesses")
    cols = st.columns(3)
    for n, biz in enumerate(results):
        with cols[n % 3]:
            biz_card(biz, f"find-{n}")
    if not results:
        st.info("No businesses match these filters.", icon=":material/search_off:")

# ---- Matches for my bookings ---------------------------------------------------------------------
with tab_match:
    if not evals:
        st.info("Book a shipment by chat or check a bookings file first — then we'll suggest buyers who want "
                "those goods.", icon=":material/join_inner:")
    else:
        options = {f"{e.booking.booking_id} · {e.booking.seller_name or 'seller'} → "
                   f"{e.booking.destination_city or '?'} ({e.badge[2:]})": e for e in evals}
        ev = options[st.selectbox("Booking", list(options))]
        b = ev.booking
        goods = ", ".join(sorted({it.description for it in b.items if it.description})) or "your goods"
        matches = match_buyers(b, directory)
        if not matches:
            st.info(f"No buyers in the directory want {goods} yet.", icon=":material/search_off:")
        else:
            st.write(f"**{len(matches)} buyer(s)** for {goods}, best match first:")
            pitch = (f"Hi, we're {b.seller_name or 'a UK seller'}. We ship {goods} from {b.origin_city or 'the UK'} "
                     f"to {b.destination_city or 'Europe'} and would like to supply you.")
            if ev.status == "Ready":
                pitch += " Our shipments are pre-checked against customs and warehouse rules."
            cols = st.columns(2)
            for n, m in enumerate(matches):
                with cols[n % 2]:
                    biz_card(m.business, f"match-{n}", m.reasons, pitch)

# ---- My listing -----------------------------------------------------------------------------------
with tab_list:
    sellers = sorted({e.booking.seller_name for e in evals if e.booking.seller_name})
    if st.session_state.my_listings:
        st.markdown("**Your listings**")
        for n, biz in enumerate(st.session_state.my_listings):
            biz_card(biz, f"mine-{n}")
    with st.form("listing_form"):
        st.markdown("**Post a listing**" if not st.session_state.my_listings else "**Post another listing**")
        c1, c2 = st.columns(2)
        with c1:
            name = st.text_input("Business name", value=sellers[0] if sellers else "")
            role = st.segmented_control("I am a", ["Seller", "Buyer"], default="Seller")
            country = st.selectbox("Country", COUNTRIES)
        with c2:
            city = st.text_input("City", placeholder="e.g. Manchester")
            booked_goods = [it.description for e in evals for it in e.booking.items if it.description]
            suggested = sorted({c for d in booked_goods for c in categories_for(d)})
            cats = st.multiselect("What you sell or buy", CATEGORIES, default=suggested[:3])
        about = st.text_area("About your business", placeholder="e.g. Ceramic mugs and tableware, ready to ship "
                                                                  "to EU retailers.")
        if st.form_submit_button("Publish listing", type="primary", icon=":material/publish:"):
            errors = [m for ok, m in ((name.strip(), "Enter your business name."),
                                      (city.strip(), "Enter your city."),
                                      (cats, "Pick at least one category.")) if not ok]
            for e in errors:
                st.error(e)
            if not errors:
                biz = Business(name=name.strip(), country=country, city=city.strip(), role=role or "Seller",
                               categories=cats, about=about.strip() or f"{role} of {', '.join(cats).lower()}.")
                st.session_state.my_listings.append(biz)
                # Demo: a matching business gets in touch, so the inbox has something to answer.
                wanted_role = "Buyer" if biz.role == "Seller" else "Seller"
                fan = next((d for d in load_directory() if d.role == wanted_role and set(d.categories) & set(cats)
                            and d.name not in threads), None)
                if fan:
                    threads[fan.name] = Thread(business=fan.name, messages=[Message(
                        sender=fan.name, sent=now(),
                        text=f"Hi {biz.name}, we saw your listing for {', '.join(cats[:2]).lower()}. "
                             f"Do you deliver to {fan.city}? We'd love to see your catalogue.")])
                st.toast("Listing published — it now appears in Find partners.", icon=":material/check_circle:")
                st.rerun()
    if sellers:
        ok = [s for s in sellers if s.lower() in prechecked]
        st.caption("Pre-checked shipper ✅ badge: " + (", ".join(ok) + " — every booking passes all 10 checks."
                   if ok else "fix every booking for a seller to earn it."))

# ---- Inbox -----------------------------------------------------------------------------------------------
with tab_inbox:
    if not threads:
        st.info("No messages yet. Send a connection request from Find partners or Matches, or post a listing.",
                icon=":material/inbox:")
    for name, t in threads.items():
        last = t.messages[-1]
        new = last.sender != "you"
        with st.expander(f"{name} — {last.text[:60]}…" if len(last.text) > 60 else f"{name} — {last.text}",
                         icon=":material/mark_email_unread:" if new else ":material/drafts:", expanded=new):
            for m in t.messages:
                with st.chat_message("user" if m.sender == "you" else "assistant",
                                     avatar=":material/person:" if m.sender == "you" else ":material/storefront:"):
                    st.caption(f"{'You' if m.sender == 'you' else m.sender} · {m.sent}")
                    st.write(m.text)
            with st.form(f"reply-{name}", clear_on_submit=True, border=False):
                reply = st.text_input("Reply", placeholder=f"Write to {name}…", label_visibility="collapsed")
                if st.form_submit_button("Send", icon=":material/send:") and reply.strip():
                    t.messages.append(Message(sender="you", text=reply.strip(), sent=now()))
                    t.messages.append(Message(sender=name, sent=now(),
                                              text="Thanks — noted. We'll get back to you within one working day."))
                    st.rerun()

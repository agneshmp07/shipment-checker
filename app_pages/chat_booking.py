"""Chat booking: describe the shipment, we ask only for what's missing."""
from datetime import date

import pandas as pd
import streamlit as st

from core import fmt, llm
from core.chat_agent import (ChatState, Extraction, ItemPatch, handle_message, is_complete, missing_fields,
                             real_issues)
from core.check import evaluate
from core.models import DESTINATION_TYPES, ITEM_ORIGIN_COUNTRIES, ORIGIN_CITIES, PRIORITIES, DESTINATIONS
from core.offline_parser import offline_extract
from ui.brand import how_to, page_title
from ui.results import carriers_or_warning, render_evaluation, status_badge

GREETING = ("Hi! Tell me about your shipment in your own words — what you're sending, how many, and from "
            "where to where. For example: *“I'm sending 1080 mugs from Manchester to a warehouse in "
            "Frankfurt.”* I'll only ask for what's missing.")

if "chat" not in st.session_state:
    st.session_state.chat = ChatState(messages=[{"role": "assistant", "content": GREETING}])
    st.session_state.ai_ok = llm.available()
    st.session_state.ai_error = "" if llm.available() else "No API key is configured."
state: ChatState = st.session_state.chat
today = date.today()

page_title("Book by chat or voice", "Describe your shipment in your own words. I'll only ask for what's "
           "missing, and the checks update every time you change something.")
how_to("chat", [
    ("Describe it", "Type or tap the mic and say what you're sending, how many, and from where to where. "
                    "Or tap one of the examples below."),
    ("Answer my questions", "I ask for at most 3 missing details at a time and check any numbers I "
                            "calculate with you (“That's 90 cartons — correct?”)."),
    ("Change anything", "Say “add a pallet” or “ready date 10-12-2026” at any time. When the booking is "
                        "complete you see the full checks, carrier and confirmation below."),
])
carriers = carriers_or_warning()
if st.session_state.ai_ok:
    st.caption(f":material/smart_toy: AI assistant: {llm.provider_label()} — it only reads your messages; "
               "every check is done by fixed rules.")
if not st.session_state.ai_ok:
    st.info(f"The AI assistant is unavailable ({st.session_state.ai_error}) — using the built-in parser, "
            "which understands simple phrases. You can also use the form below the chat. "
            "All checks work exactly the same.", icon=":material/smart_toy:")


def extract(text, s, today):
    """LLM first. A failed turn uses the offline parser; two failures in a row switch the
    AI off for the rest of the session so nobody waits on a broken connection."""
    if st.session_state.ai_ok:
        try:
            result = llm.llm_extract(text, s, today)
            st.session_state.ai_failures = 0
            return result
        except llm.LLMUnavailable as e:
            st.session_state.ai_failures = st.session_state.get("ai_failures", 0) + 1
            st.session_state.ai_error = str(e)[:120]
            if st.session_state.ai_failures >= 2:
                st.session_state.ai_ok = False
            else:
                st.toast("The AI was slow to answer, so the built-in parser read that message.",
                         icon=":material/bolt:")
    return offline_extract(text, s, today)


def phrase(s, ask, template):
    return llm.llm_phrase(s, ask, template) if st.session_state.ai_ok else None


def send(text, extractor=extract):
    with st.spinner("Updating your booking…"):
        handle_message(state, text, extractor, carriers, today, phraser=phrase)


chat_col, card_col = st.columns([3, 2], gap="large")

# ---- Chat --------------------------------------------------------------------
with chat_col:
    history = st.container(height=520)
    prompt = st.chat_input("Describe your shipment, answer a question, or change something…")
    prompt = prompt or st.session_state.pop("chat_prefill", None)      # example tapped on Home
    if len(state.messages) == 1 and not prompt:
        st.pills("Or tap an example", key="chat_example", on_change=lambda: st.session_state.update(
            chat_prefill=st.session_state.chat_example),
            options=["I'm sending 1080 mugs from Manchester to a warehouse in Frankfurt",
                     "500 cotton t-shirts from London to a shop in Paris, as fast as possible"])
    if prompt:
        send(prompt)
    with history:
        for m in state.messages:
            with st.chat_message(m["role"]):
                st.markdown(m["content"])
    if st.button("Start over", icon=":material/restart_alt:"):
        del st.session_state["chat"]
        st.rerun()

# ---- Live booking card ---------------------------------------------------------
ev = evaluate(state.booking, carriers, today)
b = state.booking
with card_col:
    with st.container(border=True):
        st.markdown("**Your booking so far**")
        if is_complete(state):
            status_badge(ev)
        else:
            to_go = len(missing_fields(state)) + len(state.pending)
            st.badge(f"In progress · {to_go} detail{'s' if to_go != 1 else ''} to go", color="gray",
                     icon=":material/pending:")

        def row(label, value, f=None):
            shown = value if value not in (None, "—", "") else ":orange[missing]"
            if f and f in {p.field for p in state.pending if p.target == "booking"}:
                shown = ":blue[to confirm]"
            st.markdown(f"{label}: **{shown}**" if shown == value else f"{label}: {shown}")

        row("From", b.origin_city and f"{b.origin_city}, {b.origin_country}")
        row("To", b.destination_city and f"{b.destination_city}, {b.destination_country}")
        row("Destination type", b.destination_type)
        row("Ready date", b.ready_date and fmt.d(b.ready_date))
        row("Priority", b.seller_priority)
        row("Pallets", b.pallets and fmt.num(b.pallets))
        row("Cartons", b.cartons and fmt.num(b.cartons), "cartons")
        row("Declared value", b.total_declared_value and fmt.money(b.total_declared_value), "total_declared_value")
        row("Gross weight", b.total_gross_weight_kg and fmt.kg(b.total_gross_weight_kg))
        if b.destination_type == "Warehouse":
            row("Delivery slot", None if b.delivery_appointment_booked is None
                else ("booked" if b.delivery_appointment_booked else "not booked"))
        row("Seller", b.seller_name)
        if b.items:
            st.dataframe(pd.DataFrame([{
                "Item": it.description or it.sku, "Qty": it.quantity, "£/unit": it.unit_price,
                "Per carton": it.units_per_carton, "Cartons": it.cartons, "kg/unit": it.unit_weight_kg,
                "HS code": it.hs_code, "Made in": it.country_of_origin} for it in b.items]), hide_index=True)
        else:
            row("Items", None)
        if ev.recommendation.winner:
            w = ev.recommendation.winner
            st.caption(f"Best carrier so far: {w.option.carrier} — {fmt.money(w.total_cost)}, "
                       f"{fmt.num(w.option.transit_days)} days")
        shown = ev.issues if is_complete(state) else real_issues(ev.issues, b)
        reds = sum(i.severity == "Red" for i in shown)
        if shown:
            st.caption(f"Checks so far: {reds} red, {len(shown) - reds} amber — "
                       + "; ".join(f"{i.rule_id} {i.title}" for i in shown))

# ---- Form fallback -------------------------------------------------------------
with st.expander("Prefer a form? Fill in or correct any field here", icon=":material/edit_note:"):
    with st.form("booking_form"):
        c1, c2, c3 = st.columns(3)
        dest_cities = [c for cs in DESTINATIONS.values() for c in cs]
        pick = lambda label, opts, cur: st.selectbox(label, opts, index=opts.index(cur) if cur in opts else None)
        with c1:
            f_origin = pick("Collection city", ORIGIN_CITIES, b.origin_city)
            f_dest = pick("Destination city", dest_cities, b.destination_city)
            f_type = pick("Destination type", DESTINATION_TYPES, b.destination_type)
        with c2:
            f_seller = st.text_input("Seller name", b.seller_name or "")
            f_date = st.date_input("Ready date", b.ready_date, format="DD/MM/YYYY")
            f_prio = pick("Priority", PRIORITIES, b.seller_priority)
            f_slot = st.selectbox("Delivery slot booked?", ["Yes", "No"],
                                  index=None if b.delivery_appointment_booked is None
                                  else (0 if b.delivery_appointment_booked else 1))
        with c3:
            f_pallets = st.number_input("Pallets", min_value=0, step=1, value=int(b.pallets) if b.pallets else None)
            f_cartons = st.number_input("Total cartons", min_value=0, step=1, value=int(b.cartons) if b.cartons else None)
            f_value = st.number_input("Declared value (£)", min_value=0.0, value=b.total_declared_value)
            f_weight = st.number_input("Gross weight (kg)", min_value=0.0, value=b.total_gross_weight_kg)
        st.markdown("Items")
        items_df = st.data_editor(pd.DataFrame([{
            "SKU": it.sku, "Description": it.description, "HS code": it.hs_code, "Quantity": it.quantity,
            "Unit price (£)": it.unit_price, "Units per carton": it.units_per_carton, "Cartons": it.cartons,
            "Unit weight (kg)": it.unit_weight_kg, "Country of origin": it.country_of_origin}
            for it in b.items] or [{"SKU": None, "Description": None, "HS code": None, "Quantity": None,
                                     "Unit price (£)": None, "Units per carton": None, "Cartons": None,
                                     "Unit weight (kg)": None, "Country of origin": None}]),
            num_rows="dynamic", hide_index=True,
            column_config={"Country of origin": st.column_config.SelectboxColumn(options=ITEM_ORIGIN_COUNTRIES),
                           "HS code": st.column_config.TextColumn()})
        if st.form_submit_button("Update booking", icon=":material/save:"):
            num = lambda v: None if v is None or pd.isna(v) else float(v)
            txt = lambda v: None if v is None or (not isinstance(v, str) and pd.isna(v)) or str(v).strip() == "" else str(v).strip()
            patches = []
            for _, r in items_df.iterrows():
                if all(txt(r[c]) is None for c in ("SKU", "Description")) and num(r["Quantity"]) is None:
                    continue
                patches.append(ItemPatch(match=txt(r["SKU"]), sku=txt(r["SKU"]), description=txt(r["Description"]),
                                         hs_code=txt(r["HS code"]), quantity=num(r["Quantity"]),
                                         unit_price=num(r["Unit price (£)"]), units_per_carton=num(r["Units per carton"]),
                                         cartons=num(r["Cartons"]), unit_weight_kg=num(r["Unit weight (kg)"]),
                                         country_of_origin=txt(r["Country of origin"])))
            kept = {p.sku for p in patches if p.sku}
            ex = Extraction(
                origin_city=f_origin, destination_city=f_dest, destination_type=f_type,
                seller_name=f_seller or None, ready_date=f_date.strftime("%d-%m-%Y") if f_date else None,
                seller_priority=f_prio, delivery_appointment_booked=None if f_slot is None else f_slot == "Yes",
                pallets=f_pallets or None, cartons=f_cartons or None, total_declared_value=f_value,
                total_gross_weight_kg=f_weight, items=patches,
                remove_items=[it.sku for it in b.items if it.sku not in kept])
            send("(Updated using the form)", extractor=lambda *_: ex)
            st.rerun()

# ---- Results + confirm -----------------------------------------------------------
if is_complete(state):
    st.divider()
    render_evaluation(ev, key="chat",
                      on_fix=lambda msg: state.messages.append({"role": "assistant", "content": msg}))
    st.divider()
    if state.confirmed:
        st.success(f"Booking {b.booking_id} is confirmed. {ev.summary}", icon=":material/task_alt:")
    elif ev.status == "Blocked":
        st.button("Confirm booking", disabled=True, icon=":material/lock:",
                  help="Fix the red issues first — tell me the correct values in the chat.")
        st.caption("Red issues must be fixed before the booking can be confirmed.")
    elif st.button("Confirm booking", type="primary", icon=":material/check:"):
        state.confirmed = True
        st.rerun()

"""One way to fix a booking: the 'Fix BK-105' window.

It shows what's wrong, then two options in the same place: 'Let us fix it' (the fixes we can make, ticked
when we're confident) and 'Or change it yourself' (only the fields behind the problems, with every field one
click away). After applying or saving it re-checks at once and offers 'Back to all problems' or 'Next problem',
so the user never loses their place.
"""
from __future__ import annotations

import math
from datetime import date

import pandas as pd
import streamlit as st

from core import fmt
from core.check import Evaluation, evaluate
from core.diagnosis import apply_fix
from core.models import ITEM_ORIGIN_COUNTRIES, PRIORITIES
from core.rules import scorecard
from ui import correct
from ui.results import get_carriers

# which fields each rule depends on: booking-level and item-level
BOOKING_FIELDS = {"R-02": ["total_declared_value"], "R-04": ["cartons"], "R-05": ["pallets", "total_gross_weight_kg"],
                  "R-07": ["total_gross_weight_kg"], "R-08": ["delivery_appointment_booked"], "R-10": ["ready_date"]}
ITEM_FIELDS = {"R-01": ["hs_code"], "R-02": ["quantity", "unit_price"], "R-03": ["quantity", "units_per_carton", "cartons"],
               "R-04": ["cartons"], "R-06": ["description"], "R-07": ["quantity", "unit_weight_kg"],
               "R-09": ["country_of_origin"]}
ITEM_COLS = {"description": "Description", "hs_code": "HS code", "quantity": "Quantity", "unit_price": "Unit price (£)",
             "units_per_carton": "Units/carton", "cartons": "Cartons", "unit_weight_kg": "Unit weight (kg)",
             "country_of_origin": "Made in"}
STATUS = {"Blocked": ("red", ":material/block:", "Can't ship yet"),
          "Warnings": ("orange", ":material/warning:", "Can ship — check the warnings"),
          "Ready": ("green", ":material/check_circle:", "Ready to ship")}


def open_fix(booking_id: str):
    """Ask the page to open the fix window for this booking on its next run."""
    st.session_state.fix_target = booking_id


def _num(v):
    return None if v is None or (isinstance(v, float) and math.isnan(v)) else float(v)


def _txt(v):
    return None if v is None or (isinstance(v, float) and math.isnan(v)) or str(v).strip() == "" else str(v).strip()


def _needed(ev: Evaluation, everything: bool) -> tuple[list[str], list[str], set]:
    """(booking fields, item fields, SKUs to show) behind this booking's problems."""
    if everything or any(i.rule_id == "DATA" for i in ev.issues):
        return (["pallets", "cartons", "total_declared_value", "total_gross_weight_kg", "ready_date",
                 "delivery_appointment_booked", "seller_priority"], list(ITEM_COLS), {it.sku for it in ev.booking.items})
    bf, itf, skus = [], [], set()
    for i in ev.issues:
        bf += [f for f in BOOKING_FIELDS.get(i.rule_id, []) if f not in bf]
        itf += [f for f in ITEM_FIELDS.get(i.rule_id, []) if f not in itf]
        if i.rule_id in ITEM_FIELDS:
            skus |= {i.item_sku} if i.item_sku else {it.sku for it in ev.booking.items}
    return bf, itf, skus


def _editor(ev: Evaluation, everything: bool) -> list[str]:
    """The 'change it yourself' form. Returns change messages after Save (else [])."""
    b = ev.booking
    bf, itf, skus = _needed(ev, everything)
    removable = everything or any(i.rule_id == "R-06" for i in ev.issues)
    with st.form(f"fix-form-{b.booking_id}-{int(everything)}", border=False):
        vals = {}
        if bf:
            cols = st.columns(min(4, len(bf)))
            for n, f in enumerate(bf):
                c = cols[n % len(cols)]
                if f == "ready_date":
                    vals[f] = c.date_input("Ready to ship", value=b.ready_date, format="DD-MM-YYYY")
                elif f == "delivery_appointment_booked":
                    v = c.selectbox("Delivery slot booked", ["Yes", "No"], index=None if b.delivery_appointment_booked is None
                                    else (0 if b.delivery_appointment_booked else 1))
                    vals[f] = None if v is None else v == "Yes"
                elif f == "seller_priority":
                    vals[f] = c.selectbox("Seller priority", PRIORITIES, index=PRIORITIES.index(b.seller_priority)
                                          if b.seller_priority in PRIORITIES else None)
                else:
                    label = {"pallets": "Pallets", "cartons": "Total cartons", "total_declared_value": "Declared value (£)",
                             "total_gross_weight_kg": "Gross weight (kg)"}[f]
                    vals[f] = c.number_input(label, min_value=0.0, value=getattr(b, f),
                                             step=1.0 if f in ("pallets", "cartons") else 10.0,
                                             format="%g" if f in ("pallets", "cartons") else "%.2f")
        items = [it for it in b.items if it.sku in skus]
        table = None
        if items and itf:
            rows = []
            for it in items:
                row = {"SKU": it.sku}
                if "description" not in itf:
                    row["Item"] = it.description
                row.update({ITEM_COLS[f]: getattr(it, f) for f in itf})
                if removable:
                    row["Remove from shipment"] = False
                rows.append(row)
            config = {"Made in": st.column_config.SelectboxColumn(options=list(ITEM_ORIGIN_COUNTRIES)),
                      "HS code": st.column_config.TextColumn(help="At least 6 digits — look it up on gov.uk/trade-tariff")}
            table = st.data_editor(pd.DataFrame(rows), hide_index=True, num_rows="fixed", disabled=["SKU", "Item"],
                                   column_config=config, key=f"fix-items-{b.booking_id}-{int(everything)}")
        saved = st.form_submit_button("Save & re-check", type="primary", icon=":material/save:")
    if not saved:
        return []
    msgs = []

    def put(obj, field, new, where=""):
        old = getattr(obj, field)
        if new != old:
            setattr(obj, field, new)
            shown = lambda v: "—" if v is None else (fmt.d(v) if isinstance(v, date) else
                                                     fmt.num(v) if isinstance(v, float) else str(v))
            msgs.append(f"{correct.NAMES.get(field, field.replace('_', ' '))}{where}: {shown(old)} → {shown(new)} (manual)")

    for f, v in vals.items():
        put(b, f, _num(v) if f in ("pallets", "cartons", "total_declared_value", "total_gross_weight_kg") else v)
    if table is not None:
        for it, (_, row) in zip(items, table.iterrows()):
            if removable and bool(row.get("Remove from shipment")):
                b.items.remove(it)
                msgs.append(f"removed {it.sku} ({it.description or 'item'}) from the shipment (manual)")
                continue
            for f in itf:
                v = row[ITEM_COLS[f]]
                new = _num(v) if f in ("quantity", "unit_price", "units_per_carton", "cartons", "unit_weight_kg") else _txt(v)
                if f == "hs_code" and new != it.hs_code:
                    it.hs_possible_leading_zero_lost = False
                put(it, f, new, f" for {it.sku}")
    return msgs


@st.dialog("Fix this booking", width="large", icon=":material/build:", on_dismiss="rerun")
def fix_dialog(booking_id: str):
    bookings = st.session_state.get("upload_bookings") or []
    b = next((x for x in bookings if x.booking_id == booking_id), None)
    if b is None:
        st.warning("That booking isn't in the file any more.")
        return
    carriers, today = get_carriers(), date.today()
    ev = evaluate(b, carriers, today)
    before = st.session_state.pop(f"fix-before-{booking_id}", None)
    colour, icon, words = STATUS[ev.status]
    score = scorecard(b, ev.issues)
    passed = sum(r["state"] == "pass" for r in score)

    st.markdown(f"### {b.booking_id} · {b.seller_name or 'Seller not set'}")
    with st.container(horizontal=True, vertical_alignment="center"):
        st.badge(words, color=colour, icon=icon)
        st.caption(f"{passed} of 10 rules passed · {b.origin_city or '?'} → {b.destination_city or '?'}")
    celebrated = bool(before and before != ev.status and ev.status == "Ready")
    if before and before != ev.status:
        if ev.status == "Ready":
            st.success(f"🎉 {b.booking_id} now passes all 10 checks — it's ready to ship.", icon=":material/celebration:")
        else:
            st.info(f"Saved and re-checked: {STATUS[before][2].lower()} → {words.lower()}.", icon=":material/refresh:")

    if ev.issues:
        st.markdown("**What's wrong**\n" + "\n".join(
            f"- {'🔴' if i.severity == 'Red' else '🟠'} **{i.title}** — {i.explanation}" for i in ev.issues))

        # ---- 1. Let us fix it
        picks = correct.suggestions(ev)
        with st.container(border=True):
            st.markdown("#### :material/auto_fix_high: Let us fix it")
            if picks:
                for s in picks:
                    st.session_state.setdefault(s["key"], s["conf"] == "High")
                    st.checkbox(f"{s['label']} {correct.CONF_BADGE[s['conf']]}", key=s["key"], help=s["why"])
                n = sum(bool(st.session_state.get(s["key"])) for s in picks)
                if st.button(f"Apply {n} fix{'es' if n != 1 else ''}", type="primary", icon=":material/check:",
                             disabled=n == 0, key=f"fix-apply-{booking_id}"):
                    st.session_state[f"fix-before-{booking_id}"] = ev.status
                    correct.apply_picks(ev, picks)
                    open_fix(booking_id)                       # re-check, keep this window open
                    st.rerun()
            else:
                st.caption("We can't fix this one automatically — it needs information only you have. "
                           "Change it below.")

        # ---- 2. Or change it yourself
        with st.container(border=True):
            st.markdown("#### :material/edit: Or change it yourself")
            everything = st.toggle("Show every field", key=f"fix-all-fields-{booking_id}")
            if not everything:
                st.caption("Only the fields behind the problems are shown.")
            if any(i.rule_id == "R-01" for i in ev.issues):
                st.caption(":material/search: Need an HS code? Look the product up on the "
                           "[UK Trade Tariff](https://www.gov.uk/trade-tariff) and enter at least 6 digits.")
            msgs = _editor(ev, everything)
            if msgs:
                correct.record({booking_id: msgs}, {booking_id: ev.status})
                st.session_state[f"fix-before-{booking_id}"] = ev.status
                open_fix(booking_id)                           # re-check, keep this window open
                st.rerun()
    elif not celebrated:
        st.success("All 10 checks pass — nothing to fix.", icon=":material/check_circle:")

    # ---- Where next
    order = [e for e in (evaluate(x, carriers, today) for x in bookings) if e.issues]
    nxt = next((e.booking.booking_id for e in order if e.booking.booking_id != booking_id), None)
    with st.container(horizontal=True):
        if st.button("← Back to all problems", key=f"fix-back-{booking_id}"):
            st.session_state.show_findings = True
            st.rerun()
        if nxt and st.button(f"Next problem: {nxt} →", type="primary" if not ev.issues else "secondary",
                             key=f"fix-next-{booking_id}"):
            open_fix(nxt)
            st.rerun()
        if not nxt:
            st.caption("That was the last booking with problems. 🎉")

"""Correcting a booking, right where its problems are shown.

In the 'What we found' pop-up each booking lists its fixes: the ones Oops-Proof can make are checkboxes
(high-confidence ones ticked), applied with one button; 'Edit by hand' opens that booking with an editor
for its fields and items. Both record what changed, so the corrected-file download and Undo keep working.
"""
from __future__ import annotations

import math
from datetime import date

import pandas as pd
import streamlit as st

from core import fmt
from core.check import Evaluation
from core.diagnosis import apply_fix, diagnose
from core.models import ITEM_ORIGIN_COUNTRIES, PRIORITIES

CONF_BADGE = {"High": ":green-badge[High confidence]", "Medium": ":blue-badge[Likely]", "Low": ":gray-badge[Check first]"}
NAMES = {"total_gross_weight_kg": "gross weight", "total_declared_value": "declared value", "unit_weight_kg": "unit weight",
         "hs_code": "HS code", "units_per_carton": "units per carton", "unit_price": "unit price",
         "delivery_appointment_booked": "delivery slot", "ready_date": "ready date"}


def _label(action: dict) -> str:
    if action.get("label") and action["label"] != "estimate":
        return action["label"]
    f, v = action["field"], action["value"]
    shown = fmt.money(v) if f in ("total_declared_value", "unit_price") else fmt.kg(v) if "weight" in f else (
        "booked" if v is True else fmt.d(date.fromisoformat(v)) if f == "ready_date" and isinstance(v, str) else
        fmt.num(v) if isinstance(v, (int, float)) else str(v))
    where = f" for {action['sku']}" if action.get("sku") else ""
    return f"Set {NAMES.get(f, f.replace('_', ' '))}{where} to {shown}"


def suggestions(ev: Evaluation) -> list[dict]:
    """The fixes we can make for one booking, in the order to apply them (items before the totals)."""
    if not ev.issues:
        return []
    out = []
    roots, rest = diagnose(ev.booking, ev.issues)
    for r in roots:
        if r.fix_action:
            out.append({"label": r.fix_label or _label(r.fix_action), "conf": r.confidence,
                        "action": r.fix_action, "why": r.title})
    for i in rest:
        if i.fix_action:
            out.append({"label": _label(i.fix_action), "conf": "Medium", "action": i.fix_action, "why": i.title})
    bid = ev.booking.booking_id
    for s in out:                                          # a stable widget key per suggestion
        a = s["action"]
        s["key"] = f"pick-{bid}-{a['target']}-{a.get('sku', '')}-{a['field']}-{a['value']}"
    return out


def record(changed: dict[str, list[str]], before: dict[str, str]):
    """Merge into the 'what changed' record the page shows (and Undo / download rely on)."""
    prev = st.session_state.get("fix_all_result") or {"changed": {}, "before": {}}
    for bid, msgs in changed.items():
        prev["changed"].setdefault(bid, []).extend(msgs)
        prev["before"].setdefault(bid, before.get(bid, "?"))
    st.session_state.fix_all_result = prev


def fix_list(ev: Evaluation, fix_lines: list[str]) -> list[dict]:
    """'What to fix' for one booking: fixes we can make become checkboxes, the rest stay as bullets.
    Returns the suggestions shown, for the Apply button."""
    picks = suggestions(ev)
    for s in picks:
        st.session_state.setdefault(s["key"], s["conf"] == "High")
    labels = [s["label"].rstrip(".").lower() for s in picks]
    manual = [ln for ln in fix_lines if ln.rstrip(".").lower() not in labels]
    for s in picks:
        st.checkbox(f"{s['label']} {CONF_BADGE[s['conf']]}", key=s["key"], help=s["why"])
    if manual:
        st.markdown("\n".join(f"- {ln}" for ln in manual))
    return picks


def apply_picks(ev: Evaluation, picks: list[dict]) -> int:
    """Apply the ticked fixes to this booking; returns how many were applied."""
    msgs = [apply_fix(ev.booking, s["action"]) for s in picks if st.session_state.get(s["key"])]
    for s in picks:
        st.session_state.pop(s["key"], None)
    if msgs:
        record({ev.booking.booking_id: msgs}, {ev.booking.booking_id: ev.status})
    return len(msgs)


def _num(v):
    return None if v is None or (isinstance(v, float) and math.isnan(v)) else float(v)


def _txt(v):
    return None if v is None or (isinstance(v, float) and math.isnan(v)) or str(v).strip() == "" else str(v).strip()


def manual_editor(ev: Evaluation, key: str):
    """Edit one booking's fields and items by hand, then re-check."""
    b, bid = ev.booking, ev.booking.booking_id
    with st.form(f"{key}-manual", border=False):
        c = st.columns(4)
        pallets = c[0].number_input("Pallets", min_value=0.0, step=1.0, value=b.pallets, format="%g")
        cartons = c[1].number_input("Total cartons", min_value=0.0, step=1.0, value=b.cartons, format="%g")
        value = c[2].number_input("Declared value (£)", min_value=0.0, step=10.0, value=b.total_declared_value)
        gross = c[3].number_input("Gross weight (kg)", min_value=0.0, step=1.0, value=b.total_gross_weight_kg)
        c = st.columns(3)
        ready = c[0].date_input("Ready to ship", value=b.ready_date, format="DD-MM-YYYY")
        slot = c[1].selectbox("Delivery slot booked", ["Yes", "No"], index=None if b.delivery_appointment_booked is None
                              else (0 if b.delivery_appointment_booked else 1))
        prio = c[2].selectbox("Seller priority", PRIORITIES,
                              index=PRIORITIES.index(b.seller_priority) if b.seller_priority in PRIORITIES else None)
        items = st.data_editor(pd.DataFrame([{
            "SKU": it.sku, "Description": it.description, "HS code": it.hs_code, "Quantity": it.quantity,
            "Unit price (£)": it.unit_price, "Units/carton": it.units_per_carton, "Cartons": it.cartons,
            "Unit weight (kg)": it.unit_weight_kg, "Made in": it.country_of_origin} for it in b.items]),
            hide_index=True, disabled=["SKU"], num_rows="fixed", key=f"{key}-items",
            column_config={"HS code": st.column_config.TextColumn(help="At least 6 digits"),
                           "Made in": st.column_config.SelectboxColumn(options=list(ITEM_ORIGIN_COUNTRIES))})
        save = st.form_submit_button("Save & re-check", type="primary", icon=":material/save:")
    if not save:
        return
    msgs = []

    def put(obj, field, new, where=""):
        old = getattr(obj, field)
        if new != old:
            setattr(obj, field, new)
            shown = lambda v: "—" if v is None else (fmt.d(v) if isinstance(v, date) else
                                                     fmt.num(v) if isinstance(v, float) else str(v))
            msgs.append(f"{NAMES.get(field, field.replace('_', ' '))}{where}: {shown(old)} → {shown(new)} (manual)")

    put(b, "pallets", _num(pallets)); put(b, "cartons", _num(cartons))
    put(b, "total_declared_value", _num(value)); put(b, "total_gross_weight_kg", _num(gross))
    put(b, "ready_date", ready); put(b, "seller_priority", prio)
    put(b, "delivery_appointment_booked", None if slot is None else slot == "Yes")
    for it, (_, row) in zip(b.items, items.iterrows()):
        where = f" for {it.sku}"
        put(it, "description", _txt(row["Description"]), where)
        new_hs = _txt(row["HS code"])
        if new_hs != it.hs_code:
            it.hs_possible_leading_zero_lost = False
        put(it, "hs_code", new_hs, where)
        for col, field in (("Quantity", "quantity"), ("Unit price (£)", "unit_price"), ("Units/carton", "units_per_carton"),
                           ("Cartons", "cartons"), ("Unit weight (kg)", "unit_weight_kg")):
            put(it, field, _num(row[col]), where)
        put(it, "country_of_origin", _txt(row["Made in"]), where)
    if msgs:
        record({bid: msgs}, {bid: ev.status})
    else:
        st.toast("Nothing changed.", icon=":material/info:")
    st.rerun()

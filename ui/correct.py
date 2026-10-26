"""'Correct your file' on the upload page: two ways to fix the bookings.

Auto-correct lists every fix Oops-Proof can suggest, each with its own checkbox (high-confidence ones
ticked), and applies only the ticked ones. Correct manually lets the user edit one booking's fields
and items directly. Both record what changed, so the corrected-file download and Undo keep working.
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


def suggestions(evals: list[Evaluation]) -> list[dict]:
    """Every fix we can suggest, in the order to apply them (item fixes before the totals they affect)."""
    out = []
    for ev in evals:
        if not ev.issues:
            continue
        roots, rest = diagnose(ev.booking, ev.issues)
        for r in roots:
            if r.fix_action:
                out.append({"bid": ev.booking.booking_id, "label": r.fix_label or _label(r.fix_action),
                            "conf": r.confidence, "action": r.fix_action, "why": r.title})
        for i in rest:
            if i.fix_action:
                out.append({"bid": ev.booking.booking_id, "label": _label(i.fix_action), "conf": "Medium",
                            "action": i.fix_action, "why": i.title})
    for s in out:                                          # a stable widget key per suggestion
        a = s["action"]
        s["key"] = f"pick-{s['bid']}-{a['target']}-{a.get('sku', '')}-{a['field']}-{a['value']}"
    return out


def _record(changed: dict[str, list[str]], before: dict[str, str]):
    """Merge into the 'what changed' record the page shows (and Undo / download rely on)."""
    prev = st.session_state.get("fix_all_result") or {"changed": {}, "before": {}}
    for bid, msgs in changed.items():
        prev["changed"].setdefault(bid, []).extend(msgs)
        prev["before"].setdefault(bid, before.get(bid, "?"))
    prev["last"] = sum(len(m) for m in changed.values())
    st.session_state.fix_all_result = prev


def _apply_selected(picks: list[dict], bookings, statuses: dict[str, str]):
    by_id = {b.booking_id: b for b in bookings}
    changed: dict[str, list[str]] = {}
    for s in picks:
        if st.session_state.get(s["key"]):
            changed.setdefault(s["bid"], []).append(apply_fix(by_id[s["bid"]], s["action"]))
    _record(changed, statuses)
    for s in picks:
        st.session_state.pop(s["key"], None)


def _select(picks: list[dict], how: str):
    for s in picks:
        st.session_state[s["key"]] = how == "all" or (how == "high" and s["conf"] == "High")


def auto_correct(evals: list[Evaluation], bookings):
    picks = suggestions(evals)
    if not picks:
        st.success("Nothing left that can be corrected automatically. Anything still flagged needs your "
                   "decision — switch to **Correct manually**.", icon=":material/check_circle:")
        return
    for s in picks:
        st.session_state.setdefault(s["key"], s["conf"] == "High")
    st.caption("Tick the fixes to apply. High-confidence ones are ticked for you; the others are likely but "
               "worth a look. Nothing changes until you press Apply.")
    statuses = {ev.booking.booking_id: ev.status for ev in evals}
    with st.container(horizontal=True):
        st.button("Select all", type="tertiary", icon=":material/done_all:", on_click=_select, args=(picks, "all"))
        st.button("Only high confidence", type="tertiary", icon=":material/verified:", on_click=_select,
                  args=(picks, "high"))
        st.button("Clear", type="tertiary", icon=":material/remove_done:", on_click=_select, args=(picks, "none"))
    current = None
    for s in picks:
        if s["bid"] != current:
            current = s["bid"]
            st.markdown(f"**{current}** · {statuses[current].replace('Warnings', 'Warnings').lower()}")
        st.checkbox(f"{s['label']} {CONF_BADGE[s['conf']]}", key=s["key"], help=s["why"])
    n = sum(bool(st.session_state.get(s["key"])) for s in picks)
    st.button(f"Apply selected ({n})", type="primary", icon=":material/auto_fix_high:", disabled=n == 0,
              on_click=_apply_selected, args=(picks, bookings, statuses))


def _num(v):
    return None if v is None or (isinstance(v, float) and math.isnan(v)) else float(v)


def _txt(v):
    return None if v is None or (isinstance(v, float) and math.isnan(v)) or str(v).strip() == "" else str(v).strip()


def correct_manually(evals: list[Evaluation], bookings):
    order = sorted(evals, key=lambda e: {"Blocked": 0, "Warnings": 1, "Ready": 2}[e.status])
    ids = [e.booking.booking_id for e in order]
    focus = st.session_state.get("focus_booking")
    bid = st.selectbox("Booking to correct", ids, index=ids.index(focus) if focus in ids else 0,
                       format_func=lambda i: f"{i} · {next(e.badge for e in evals if e.booking.booking_id == i)}",
                       key="manual_booking")
    ev = next(e for e in evals if e.booking.booking_id == bid)
    b = ev.booking
    if ev.issues:
        st.markdown("\n".join(f"- :{'red' if i.severity == 'Red' else 'orange'}[{i.title}] — {i.explanation}"
                              for i in ev.issues[:6]))
    else:
        st.caption("This booking passes all 10 checks — edit only if something is wrong in real life.")
    with st.form(f"manual-{bid}", border=False):
        c = st.columns(4)
        pallets = c[0].number_input("Pallets", min_value=0.0, step=1.0, value=b.pallets, format="%g")
        cartons = c[1].number_input("Total cartons", min_value=0.0, step=1.0, value=b.cartons, format="%g")
        value = c[2].number_input("Declared value (£)", min_value=0.0, step=10.0, value=b.total_declared_value)
        gross = c[3].number_input("Gross weight (kg)", min_value=0.0, step=1.0, value=b.total_gross_weight_kg)
        c = st.columns(3)
        ready = c[0].date_input("Ready to ship", value=b.ready_date, format="DD-MM-YYYY")
        slot_opts = ["Yes", "No"]
        slot = c[1].selectbox("Delivery slot booked", slot_opts, index=None if b.delivery_appointment_booked is None
                              else (0 if b.delivery_appointment_booked else 1))
        prio = c[2].selectbox("Seller priority", PRIORITIES,
                              index=PRIORITIES.index(b.seller_priority) if b.seller_priority in PRIORITIES else None)
        items = st.data_editor(pd.DataFrame([{
            "SKU": it.sku, "Description": it.description, "HS code": it.hs_code, "Quantity": it.quantity,
            "Unit price (£)": it.unit_price, "Units/carton": it.units_per_carton, "Cartons": it.cartons,
            "Unit weight (kg)": it.unit_weight_kg, "Made in": it.country_of_origin} for it in b.items]),
            hide_index=True, disabled=["SKU"], num_rows="fixed", key=f"items-{bid}",
            column_config={"HS code": st.column_config.TextColumn(help="At least 6 digits"),
                           "Made in": st.column_config.SelectboxColumn(options=list(ITEM_ORIGIN_COUNTRIES))})
        save = st.form_submit_button("Save & re-check", type="primary", icon=":material/save:")
    if not save:
        return
    msgs, before = [], ev.status
    def put(obj, field, new, where=""):
        old = getattr(obj, field)
        if new != old and not (old is None and new is None):
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
        _record({bid: msgs}, {bid: before})
        st.session_state.focus_booking = bid
    else:
        st.toast("Nothing changed.", icon=":material/info:")
    st.rerun()


def render(evals: list[Evaluation], bookings):
    with st.container(border=True):
        st.markdown("#### Correct your file")
        mode = st.segmented_control("How do you want to correct it?", ["Auto-correct", "Correct manually"],
                                    default="Auto-correct", key="correct_mode", label_visibility="collapsed")
        if mode == "Correct manually":
            correct_manually(evals, bookings)
        else:
            auto_correct(evals, bookings)

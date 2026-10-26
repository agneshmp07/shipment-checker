"""The fixes Oops-Proof can make for a booking, applying the ones the user ticks, and recording every
change (so the corrected-file download, 'See what was corrected' and Undo keep working).
Used by the 'Fix this booking' window (ui/fixflow.py)."""
from __future__ import annotations

from datetime import date

import streamlit as st

from core import fmt
from core.check import Evaluation
from core.diagnosis import apply_fix, diagnose

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


def apply_picks(ev: Evaluation, picks: list[dict]) -> int:
    """Apply the ticked fixes to this booking; returns how many were applied."""
    msgs = [apply_fix(ev.booking, s["action"]) for s in picks if st.session_state.get(s["key"])]
    for s in picks:
        st.session_state.pop(s["key"], None)
    if msgs:
        record({ev.booking.booking_id: msgs}, {ev.booking.booking_id: ev.status})
    return len(msgs)

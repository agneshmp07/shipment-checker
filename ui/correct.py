"""The fixes Oops-Proof can make for a booking, applying the ones the user ticks, and recording every
change (so the corrected-file download, 'See what was corrected' and Undo keep working).
Used by the 'Fix this booking' window (ui/fixflow.py)."""
from __future__ import annotations

from datetime import date

import streamlit as st

from core import fmt
from core.check import Evaluation
from core.diagnosis import apply_fix, high_confidence_actions

CONF_BADGE = {"High": ":green-badge[Certain]"}
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
    """The fixes we're certain of for one booking, items before the totals: High-confidence root causes,
    misspellings ('Germny' -> 'Germany') and an HS code that lost its leading zero in Excel.

    Guesses are never offered: facts only the seller knows (a booked delivery slot, the ready date, an HS
    code that's missing) are left for the person to enter."""
    if not ev.issues:
        return []
    out = [{"label": getattr(r, "fix_label", None) or _label(a), "conf": "High", "action": a, "why": r.title}
           for r, a in high_confidence_actions(ev.booking, ev.issues)]
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

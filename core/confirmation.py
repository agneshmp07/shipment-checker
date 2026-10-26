"""Plain-English confirmation, estimated delivery date and 'what happens next'."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from core import fmt
from core.carriers import label
from core.models import Booking, Issue, Recommendation

DELIVERY_ASSUMPTION = ("Estimated delivery = ready date + transit days, counted as calendar days "
                       "(weekends included). The carrier confirms the exact date at collection.")


def delivery_date(b: Booking, rec: Recommendation) -> Optional[date]:
    if b.ready_date is None or rec.winner is None:
        return None
    return b.ready_date + timedelta(days=int(rec.winner.option.transit_days))


def _units(b: Booking) -> Optional[float]:
    if b.items and all(it.quantity is not None for it in b.items):
        return sum(it.quantity for it in b.items)
    return None


def summary(b: Booking, rec: Recommendation, issues: list[Issue]) -> str:
    """One paragraph a seller can read, e.g. 'Your 90 cartons (1,080 units) on 3 pallets ...'."""
    if rec.winner is None:
        return f"We can't confirm a carrier yet. {rec.reason}"
    units = _units(b)
    what = f"Your {fmt.num(b.cartons)} cartons" if b.cartons is not None else "Your goods"
    if units is not None:
        what += f" ({fmt.num(units)} units)"
    pallets = f"{fmt.num(b.pallets)} pallet{'s' if b.pallets != 1 else ''}"
    eta = delivery_date(b, rec)
    text = (f"{what} on {pallets} will be collected from {b.origin_city or '?'} on {fmt.d(b.ready_date)} "
            f"by {label(rec.winner.option)} and should arrive in {b.destination_city or '?'} around "
            f"{fmt.d(eta)}. Cost: {fmt.money(rec.winner.total_cost)}.")
    reds = sum(i.severity == "Red" for i in issues)
    if reds:
        text = f"Once the {reds} red issue{'s are' if reds != 1 else ' is'} fixed: " + text[0].lower() + text[1:]
    return text


def next_steps(b: Booking, rec: Recommendation, issues: list[Issue]) -> list[dict]:
    """Timeline of {'step', 'detail', 'state'} where state is 'todo', 'warn' or 'done'."""
    reds = [i for i in issues if i.severity == "Red"]
    ambers = [i for i in issues if i.severity == "Amber" and i.rule_id != "R-08"]
    steps = []
    if reds:
        steps.append({"step": "Fix red issues", "state": "todo",
                      "detail": f"{len(reds)} issue{'s' if len(reds) != 1 else ''} must be fixed before "
                                "the shipment can leave: " + "; ".join(sorted({i.title for i in reds})) + "."})
    if ambers:
        steps.append({"step": "Review warnings", "state": "warn",
                      "detail": "; ".join(sorted({i.title for i in ambers})) + "."})
    if b.destination_type == "Warehouse":
        booked = b.delivery_appointment_booked is True
        steps.append({"step": "Book the delivery slot", "state": "done" if booked else "todo",
                      "detail": "Delivery slot at the warehouse is booked." if booked else
                      f"Book a time slot with the receiving warehouse in {b.destination_city or '?'} "
                      "before collection."})
    steps.append({"step": "Label cartons", "state": "todo",
                  "detail": f"Label all {fmt.num(b.cartons)} cartons with the booking ID {b.booking_id or ''}, "
                            "SKU and carton number (e.g. 1 of "
                            f"{fmt.num(b.cartons)}), so the warehouse can count them. Print the carton labels below."})
    steps.append({"step": "Prepare the commercial invoice", "state": "todo",
                  "detail": "The document customs relies on: every item with its description, HS code, "
                            f"country of origin, quantity and value — total {fmt.money(b.total_declared_value)}. "
                            "Oops-Proof drafts it for you below (PDF or Excel)."})
    if rec.winner:
        c = rec.winner.option
        steps.append({"step": "Collection", "state": "todo",
                      "detail": f"{label(c)} collects {fmt.num(b.pallets)} pallet(s) from "
                                f"{b.origin_city or '?'} on {fmt.d(b.ready_date)}."})
        steps.append({"step": "Delivery", "state": "todo",
                      "detail": f"Arrives in {b.destination_city or '?'} around {fmt.d(delivery_date(b, rec))} "
                                f"({fmt.num(c.transit_days)} calendar days in transit)."})
    return steps

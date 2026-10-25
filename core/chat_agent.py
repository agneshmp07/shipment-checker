"""Chat booking engine.

Flow per user message:
  1. An extractor (LLM, or the offline parser if the API is unavailable) turns the
     text into an Extraction: only the fields the user stated or changed.
  2. Code merges it into the Booking, validating every value against the allowed lists.
  3. Code works out what's still missing and what it can calculate but must confirm
     ("That's 90 cartons — correct?").
  4. Code re-runs all checks + carrier recommendation and writes a change summary.
The LLM never decides pass/fail; it only extracts and (optionally) phrases questions.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date
from typing import Callable, Optional

from pydantic import BaseModel, Field, field_validator

from core import fmt
from core.check import Evaluation, evaluate
from core.rules import TITLES as TITLES_BY_RULE
from core.excel_loader import match_choice, parse_date
from core.models import (
    DESTINATIONS, DESTINATION_TYPES, ITEM_ORIGIN_COUNTRIES, ORIGIN_CITIES, PRIORITIES,
    Booking, CarrierOption, Item,
)

# ---- What the extractor returns -------------------------------------------


def _finite(v):
    return v if v is None or math.isfinite(v) else None     # NaN / infinity: treat as not said


class ItemPatch(BaseModel):
    """New item, or changes to an existing one."""
    match: Optional[str] = Field(None, description="SKU or description of the existing item this "
                                 "changes; null for a new item or when only one item exists")
    sku: Optional[str] = None
    description: Optional[str] = None
    hs_code: Optional[str] = None
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    units_per_carton: Optional[float] = None
    cartons: Optional[float] = None
    unit_weight_kg: Optional[float] = None
    country_of_origin: Optional[str] = None

    _numbers = field_validator("quantity", "unit_price", "units_per_carton", "cartons", "unit_weight_kg")(
        lambda v: _finite(v))


class Extraction(BaseModel):
    """Only what the user said in THIS message; everything else null."""
    seller_name: Optional[str] = None
    origin_city: Optional[str] = None
    destination_city: Optional[str] = None
    destination_type: Optional[str] = None
    ready_date: Optional[str] = Field(None, description="DD-MM-YYYY")
    seller_priority: Optional[str] = None
    pallets: Optional[float] = None
    cartons: Optional[float] = None
    total_declared_value: Optional[float] = None
    total_gross_weight_kg: Optional[float] = None
    delivery_appointment_booked: Optional[bool] = None
    items: list[ItemPatch] = Field(default_factory=list)
    remove_items: list[str] = Field(default_factory=list)
    confirms_proposal: Optional[bool] = Field(None, description="true if the user accepts the "
                                              "calculated values we proposed, false if they reject them")
    unknown_fields: list[str] = Field(default_factory=list, description="fields the user says they don't "
                                      "know, e.g. ['hs_code'] or ['country_of_origin']")

    _numbers = field_validator("pallets", "cartons", "total_declared_value", "total_gross_weight_kg")(
        lambda v: _finite(v))


# ---- Field labels and question order --------------------------------------

LABELS = {
    "origin_city": "collection city (London, Manchester, Birmingham or Leeds)",
    "destination_city": "destination city (Berlin, Frankfurt, Hamburg, Paris, Lyon, Amsterdam or Rotterdam)",
    "destination_type": "whether it's going to a warehouse or a business address",
    "description": "what the goods are",
    "quantity": "how many units",
    "unit_price": "the price per unit (£)",
    "units_per_carton": "how many units go in each carton",
    "unit_weight_kg": "the weight of one unit (kg)",
    "hs_code": "the HS code (the customs code for the product, at least 6 digits)",
    "country_of_origin": "where it was made (United Kingdom, China, India, Vietnam, Turkey or Germany)",
    "cartons": "how many cartons",
    "pallets": "how many pallets",
    "total_gross_weight_kg": "the total gross weight in kg (goods + cartons + pallets)",
    "total_declared_value": "the total declared value (£)",
    "ready_date": "the date the goods are ready for collection (DD-MM-YYYY)",
    "seller_priority": "what matters most: cheapest, fastest, most reliable or balanced",
    "seller_name": "your business name",
    "delivery_appointment_booked": "whether you've booked a delivery slot at the warehouse",
}
BOOKING_ORDER_A = ["origin_city", "destination_city", "destination_type"]
ITEM_ORDER = ["description", "quantity", "unit_price", "units_per_carton", "unit_weight_kg",
              "hs_code", "country_of_origin", "cartons"]
BOOKING_ORDER_B = ["pallets", "total_gross_weight_kg", "cartons", "total_declared_value", "ready_date",
                   "seller_priority", "seller_name", "delivery_appointment_booked"]
SKIPPABLE = {"hs_code", "country_of_origin"}      # rules flag them; don't nag forever
MAX_ASKS = 2
FIELDS_PER_QUESTION = 3


@dataclass
class Proposal:
    """A value we calculated and want the user to confirm."""
    target: str              # "booking" or an item SKU
    field: str
    value: float
    why: str                 # "1,080 ÷ 12"


@dataclass
class ChatState:
    booking: Booking = field(default_factory=lambda: Booking(booking_id="CHAT-001"))
    pending: list[Proposal] = field(default_factory=list)
    ask_counts: dict[str, int] = field(default_factory=dict)
    last_asked: list[str] = field(default_factory=list)       # missing-field keys asked last turn
    ask_first: set[str] = field(default_factory=set)          # keys to ask next (rejected proposals)
    messages: list[dict] = field(default_factory=list)        # {"role", "content"}
    confirmed: bool = False


# ---- Merge -----------------------------------------------------------------


def _clean_choice(value, allowed, label, problems) -> Optional[str]:
    if value is None:
        return None
    match = match_choice(value, allowed)
    if match is None:
        problems.append(f"I can't use “{value}” for {label}. Please choose one of: {', '.join(allowed)}.")
    return match


def _find_item(b: Booking, patch: ItemPatch) -> Optional[Item]:
    keys = [k.lower() for k in (patch.match, patch.sku) if k]
    for it in b.items:
        for k in keys:
            if k == (it.sku or "").lower() or k in (it.description or "").lower():
                return it
    if patch.description and not keys:
        for it in b.items:
            d = (it.description or "").lower()
            if d and (patch.description.lower() in d or d in patch.description.lower()):
                return it
        return None                          # a new product
    return b.items[-1] if b.items else None  # "it's 12 per carton" -> the item we're discussing


def merge(state: ChatState, ex: Extraction, today: date) -> list[str]:
    """Apply an Extraction to the booking. Returns polite rejection messages."""
    b, problems = state.booking, []

    # Accept / reject calculated proposals first; explicit values below override them.
    if ex.confirms_proposal is True:
        for p in state.pending:
            _apply(b, p.target, p.field, p.value)
    elif ex.confirms_proposal is False:
        for p in state.pending:
            state.ask_counts[p.field] = 0       # ask for it directly instead
            state.ask_counts[f"reject:{p.target}:{p.field}"] = 1
            state.ask_first.add(p.field if p.target == "booking" else f"{p.target}:{p.field}")
    state.pending = []

    b.seller_name = ex.seller_name.strip() if ex.seller_name else b.seller_name
    if ex.origin_city:
        b.origin_city = _clean_choice(ex.origin_city, ORIGIN_CITIES, "the collection city", problems) or b.origin_city
    if ex.destination_city:
        all_cities = [c for cs in DESTINATIONS.values() for c in cs]
        city = _clean_choice(ex.destination_city, all_cities, "the destination city", problems)
        if city:
            b.destination_city = city
            b.destination_country = next(k for k, v in DESTINATIONS.items() if city in v)
    if ex.destination_type:
        b.destination_type = _clean_choice(ex.destination_type, DESTINATION_TYPES, "the destination type",
                                           problems) or b.destination_type
    if ex.seller_priority:
        b.seller_priority = _clean_choice(ex.seller_priority, PRIORITIES, "the priority", problems) or b.seller_priority
    if ex.ready_date:
        d, err = parse_date(ex.ready_date)
        if err:
            problems.append(f"I couldn't read the date “{ex.ready_date}”. Please use DD-MM-YYYY, e.g. "
                            f"{fmt.d(today)}.")
        else:
            b.ready_date = d
    for f in ("pallets", "cartons", "total_declared_value", "total_gross_weight_kg"):
        v = getattr(ex, f)
        if v is not None:
            if v < 0 or (f == "pallets" and v == 0):
                problems.append(f"{f.replace('_', ' ').capitalize()} can't be {fmt.num(v)}.")
            else:
                setattr(b, f, v)
    if ex.delivery_appointment_booked is not None:
        b.delivery_appointment_booked = ex.delivery_appointment_booked

    for name in ex.remove_items:
        b.items = [it for it in b.items
                   if name.lower() not in ((it.sku or "").lower(), (it.description or "").lower())]

    for f in ex.unknown_fields:
        blank = [it for it in b.items if not getattr(it, f)]
        if f in SKIPPABLE and blank:            # stop asking; the rules will flag it instead
            for it in blank:
                state.ask_counts[f"{it.sku}:{f}"] = MAX_ASKS
            what = "HS code" if f == "hs_code" else "country of origin"
            tip = " You can look it up at gov.uk/trade-tariff." if f == "hs_code" else ""
            problems.append(f"No problem — I'll leave the {what} blank for now. It will show as an issue to "
                            f"fix before shipping.{tip}")

    for patch in ex.items:
        it = _find_item(b, patch)
        if it is None:
            it = Item(booking_id=b.booking_id, sku=patch.sku or f"ITEM-{len(b.items) + 1:02d}")
            b.items.append(it)
        for f in ("description", "hs_code", "quantity", "unit_price", "units_per_carton", "cartons",
                  "unit_weight_kg"):
            v = getattr(patch, f)
            if v is not None:
                setattr(it, f, str(v).strip() if f in ("description", "hs_code") else v)
        if patch.sku and patch.match:
            it.sku = patch.sku
        if patch.country_of_origin:
            it.country_of_origin = _clean_choice(patch.country_of_origin, ITEM_ORIGIN_COUNTRIES,
                                                 f"where {it.description or it.sku} was made",
                                                 problems) or it.country_of_origin
    return problems


def _apply(b: Booking, target: str, f: str, value: float):
    if target == "booking":
        setattr(b, f, value)
    else:
        for it in b.items:
            if it.sku == target:
                setattr(it, f, value)


# ---- Missing fields and proposals -----------------------------------------


def proposals(state: ChatState) -> list[Proposal]:
    """Values we can calculate but must confirm, unless the user already rejected them."""
    b, out = state.booking, []
    rejected = lambda t, f: state.ask_counts.get(f"reject:{t}:{f}")
    for it in b.items:
        if (it.cartons is None and it.quantity and it.units_per_carton
                and (it.quantity / it.units_per_carton).is_integer() and not rejected(it.sku, "cartons")):
            out.append(Proposal(it.sku, "cartons", it.quantity / it.units_per_carton,
                                f"{fmt.num(it.quantity)} ÷ {fmt.num(it.units_per_carton)}"))
    if b.items and not out:      # booking totals only once item cartons are settled
        if b.cartons is None and all(it.cartons is not None for it in b.items) and not rejected("booking", "cartons"):
            out.append(Proposal("booking", "cartons", sum(it.cartons for it in b.items),
                                "sum of the item cartons"))
        if (b.total_declared_value is None and all(it.quantity is not None and it.unit_price is not None
                                                   for it in b.items)
                and not rejected("booking", "total_declared_value")):
            out.append(Proposal("booking", "total_declared_value",
                                round(sum(it.quantity * it.unit_price for it in b.items), 2),
                                " + ".join(f"{fmt.num(it.quantity)} × {fmt.money(it.unit_price)}" for it in b.items)))
    return out


def missing_fields(state: ChatState) -> list[tuple[str, str, Optional[str]]]:
    """[(key, field, item_sku)] still needed, in question order. key is unique per item."""
    b, out = state.booking, []
    proposed = {(p.target, p.field) for p in state.pending}

    def need(f, value, sku=None):
        key = f"{sku}:{f}" if sku else f
        if value is not None and value != "":
            return
        if ((sku or "booking"), f) in proposed:
            return
        if f in SKIPPABLE and state.ask_counts.get(key, 0) >= MAX_ASKS:
            return
        out.append((key, f, sku))

    for f in BOOKING_ORDER_A:
        need(f, getattr(b, f))
    if not b.items:
        for f in ("description", "quantity"):
            out.append((f"new:{f}", f, None))
    for it in b.items:
        for f in ITEM_ORDER:
            need(f, getattr(it, f), it.sku)
    for f in BOOKING_ORDER_B:
        if f == "delivery_appointment_booked" and b.destination_type != "Warehouse":
            continue
        need(f, getattr(b, f))
    out.sort(key=lambda m: m[0] not in state.ask_first)    # stable: rejected proposals first
    return out


def is_complete(state: ChatState) -> bool:
    return not missing_fields(state) and not state.pending


# ---- Questions ---------------------------------------------------------------


def template_question(state: ChatState, ask: list[tuple[str, str, Optional[str]]]) -> str:
    """Plain question without the LLM."""
    parts, calc = [], []
    for p in state.pending:
        if p.field == "total_declared_value":
            calc.append(f"a total declared value of {fmt.money(p.value)} ({p.why})")
        elif p.target == "booking":
            calc.append(f"{fmt.num(p.value)} cartons in total ({p.why})")
        else:
            calc.append(f"{fmt.num(p.value)} cartons of {_item_name(state.booking, p.target)} ({p.why})")
    if calc:
        parts.append("By my maths that's " + " and ".join(calc) + " — correct?")
    if ask:
        groups: dict[Optional[str], list[str]] = {}         # questions grouped by product (None = booking)
        for _, f, sku in ask:
            key = sku if sku and len(state.booking.items) > 1 and f != "description" else None
            groups.setdefault(key, []).append(LABELS[f])
        for key, names in groups.items():
            joined = names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]
            lead = f"For the {_item_name(state.booking, key)}, could" if key else "Could"
            parts.append(f"{lead} you tell me {joined}?")
    return " ".join(parts)


def _item_name(b: Booking, sku: str) -> str:
    it = next((i for i in b.items if i.sku == sku), None)
    return (it.description or it.sku) if it else sku


# ---- Change summary ------------------------------------------------------------

SUMMARY_FIELDS = {
    "seller_name": "seller", "origin_city": "from", "destination_city": "to", "destination_type": "type",
    "ready_date": "ready date", "seller_priority": "priority", "pallets": "pallets", "cartons": "cartons",
    "total_declared_value": "declared value", "total_gross_weight_kg": "gross weight",
    "delivery_appointment_booked": "delivery slot",
}


def _show(f: str, v) -> str:
    if v is None:
        return "—"
    if f in ("total_declared_value", "unit_price"):
        return fmt.money(v)
    if f in ("total_gross_weight_kg", "unit_weight_kg"):
        return fmt.kg(v)
    if f == "ready_date":
        return fmt.d(v)
    if f == "delivery_appointment_booked":
        return "booked" if v else "not booked"
    if isinstance(v, float):
        return fmt.num(v)
    return str(v)


def real_issues(issues: list, b: Booking) -> list:
    """While chatting, drop issues that only exist because we haven't asked yet."""
    def not_asked_yet(i) -> bool:
        it = next((x for x in b.items if x.sku == i.item_sku), None)
        if i.rule_id == "R-01":
            return it is not None and not it.hs_code
        if i.rule_id == "R-09":
            return True
        if i.rule_id == "R-08":
            return b.delivery_appointment_booked is None
        return i.rule_id == "DATA"
    return [i for i in issues if not not_asked_yet(i)]


def _added(f: str, v, name: str = "") -> str:
    """A newly given value in plain words: 'from Manchester', '1,080 mugs', '£5.00 each'."""
    phrases = {
        "seller_name": lambda: f"seller {v}", "origin_city": lambda: f"from {v}", "destination_city": lambda: f"to {v}",
        "destination_type": lambda: str(v).lower(), "ready_date": lambda: f"ready {fmt.d(v)}",
        "seller_priority": lambda: f"{str(v).lower()} option", "pallets": lambda: f"{fmt.num(v)} pallet{'s' if v != 1 else ''}",
        "cartons": lambda: f"{fmt.num(v)} cartons in total", "total_declared_value": lambda: f"{fmt.money(v)} declared",
        "total_gross_weight_kg": lambda: f"{fmt.kg(v)} gross", "delivery_appointment_booked":
            lambda: "delivery slot booked" if v else "no delivery slot yet",
        "quantity": lambda: f"{fmt.num(v)} {name}", "unit_price": lambda: f"{fmt.money(v)} each",
        "units_per_carton": lambda: f"{fmt.num(v)} per carton", "item_cartons": lambda: f"{fmt.num(v)} cartons of {name}",
        "unit_weight_kg": lambda: f"{fmt.kg(v)} each", "hs_code": lambda: f"HS code {v}",
        "country_of_origin": lambda: f"made in {v}",
    }
    return phrases[f]()


def change_summary(before: Booking, before_ev: Evaluation, after: Booking, after_ev: Evaluation,
                   complete: bool = True, was_complete: bool = False) -> str:
    """'Got it: …' for newly given details, 'Updated: old → new' for changed ones, plus what that did
    to weight per pallet, cost, carrier and the checks."""
    added, changes = [], []
    for f, label in SUMMARY_FIELDS.items():
        old, new = getattr(before, f), getattr(after, f)
        if old != new:
            if old is None:
                added.append(_added(f, new))
            else:
                changes.append(f"{label} {_show(f, old)} → {_show(f, new)}")
    old_items = {i.sku: i for i in before.items}
    new_skus = {i.sku for i in after.items}
    for gone in before.items:
        if gone.sku not in new_skus:
            changes.append(f"removed {gone.description or gone.sku}")
    several = len(after.items) > 1
    for it in after.items:
        prev = old_items.get(it.sku)
        name = it.description or it.sku
        for f in ("quantity", "unit_price", "units_per_carton", "cartons", "unit_weight_kg",
                  "hs_code", "country_of_origin"):
            old, new = (getattr(prev, f) if prev else None), getattr(it, f)
            if old != new:
                if old is None:
                    phrase = _added("item_cartons" if f == "cartons" else f, new, name)
                    if several and f not in ("quantity", "cartons"):
                        phrase = f"{name} {phrase}"          # say which product the value belongs to
                    added.append(phrase)
                else:
                    label = f.replace("_kg", "").replace("_", " ")
                    changes.append(f"{name} {label} {_show(f, old)} → {_show(f, new)}")
        if prev is None and it.quantity is None:
            added.append(name)
    if not added and not changes:
        return ""
    effects = []
    r0, r1 = before_ev.recommendation, after_ev.recommendation
    c0 = r0.winner.total_cost if r0.winner else None
    c1 = r1.winner.total_cost if r1.winner else None
    if changes:
        if r0.weight_per_pallet != r1.weight_per_pallet and r1.weight_per_pallet is not None and r0.weight_per_pallet:
            effects.append(f"weight per pallet {fmt.kg(r0.weight_per_pallet)} → {fmt.kg(r1.weight_per_pallet)}")
        if c1 is not None and c0 is not None and c0 != c1:
            effects.append(f"cost {fmt.money(c0)} → {fmt.money(c1)}")
    if r1.winner and (not r0.winner or r0.winner.option != r1.winner.option):
        effects.append(f"best carrier: {r1.winner.option.carrier}, {fmt.money(c1)}")
    # "Missing because not asked yet" is never news, before or (mid-conversation) after.
    old_issues = before_ev.issues if was_complete else real_issues(before_ev.issues, before)
    new_all = after_ev.issues if complete else real_issues(after_ev.issues, after)
    old_rules = {i.rule_id for i in old_issues}
    new_issues = [i for i in new_all if i.rule_id not in old_rules]
    fixed = old_rules - {i.rule_id for i in new_all}
    if complete and not new_all:
        checks = "checks: all passing ✅"
    elif complete:
        checks = f"checks: {after_ev.badge}"
    else:
        checks = ""
    if new_issues:
        checks += (" — new: " if checks else "heads-up: ") + " ".join(i.explanation for i in new_issues)
    if fixed:
        checks += (" — fixed: " if checks else "fixed: ") + ", ".join(TITLES_BY_RULE.get(r, r) for r in sorted(fixed))
    tail = effects + ([checks] if checks else [])
    lines = []
    if changes:
        lines.append("Updated: " + " · ".join(changes + tail))
    if added:
        lines.append("Got it: " + " · ".join(added + ([] if changes else tail)))
    return "\n\n".join(lines)


# ---- One turn --------------------------------------------------------------------

Extractor = Callable[[str, ChatState, date], Extraction]
Phraser = Callable[[ChatState, list, str], Optional[str]]


def handle_message(state: ChatState, text: str, extractor: Extractor, carriers: list[CarrierOption],
                   today: Optional[date] = None, phraser: Optional[Phraser] = None) -> str:
    """Process one user message; returns the assistant reply (also appended to state.messages)."""
    today = today or date.today()
    state.messages.append({"role": "user", "content": text})
    before = state.booking.model_copy(deep=True)
    before_ev = evaluate(before, carriers, today)
    was_complete = is_complete(state)

    ex = extractor(text, state, today)
    problems = merge(state, ex, today)
    after_ev = evaluate(state.booking, carriers, today)
    state.pending = proposals(state)
    summary = change_summary(before, before_ev, state.booking, after_ev, complete=is_complete(state),
                             was_complete=was_complete)

    missing = missing_fields(state)
    ask = missing[:FIELDS_PER_QUESTION] if not state.pending else missing[:max(0, FIELDS_PER_QUESTION - 1)]
    for key, _, _ in ask:
        state.ask_counts[key] = state.ask_counts.get(key, 0) + 1
    state.last_asked = [f for _, f, _ in ask]

    parts = []
    if summary:
        parts.append(summary)
    parts.extend(problems)
    if state.pending or ask:
        question = template_question(state, ask)
        if phraser:
            question = phraser(state, ask, question) or question
        parts.append(question)
    elif not summary and not problems:
        parts.append("I didn't catch any booking details in that. You can change anything — for example "
                     "“add a pallet” or “ready date 10-12-2026”.")
    if is_complete(state):
        reds = sum(i.severity == "Red" for i in after_ev.issues)
        ambers = len(after_ev.issues) - reds
        if after_ev.status == "Ready":
            parts.append("Your booking is complete — 🟢 Ready to ship. The full check results are shown below.")
        elif after_ev.status == "Warnings":
            parts.append(f"Your booking is complete — 🟠 ready to ship, with {ambers} warning"
                         f"{'s' if ambers != 1 else ''} to check below.")
        else:
            parts.append(f"All the details are in — 🔴 {reds} issue{'s' if reds != 1 else ''} must be fixed "
                         "before it can ship. See the checks below for exactly what to change.")
    reply = "\n\n".join(parts)
    state.messages.append({"role": "assistant", "content": reply})
    return reply

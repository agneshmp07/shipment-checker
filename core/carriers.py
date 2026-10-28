"""Carrier rate card (Sheet 3): load, filter by route and pallet weight, rank by priority."""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Optional

from core import fmt
from core.models import Booking, CarrierOption, CarrierResult, Recommendation

CARRIERS_PATH = Path(__file__).resolve().parent.parent / "data" / "carriers.json"

BALANCED_WEIGHTS = {"cost": 0.4, "speed": 0.3, "reliability": 0.3}


def load_carriers(path: Path | None = None) -> list[CarrierOption]:
    """Read data/carriers.json (or $SHIPMENT_CARRIERS_PATH). Returns [] if missing."""
    path = Path(path or os.environ.get("SHIPMENT_CARRIERS_PATH") or CARRIERS_PATH)
    if not path.exists():
        return []
    return [CarrierOption(**row) for row in json.loads(path.read_text(encoding="utf-8"))]


def label(c: CarrierOption) -> str:
    return f"{c.carrier} ({c.service})"


def weight_per_pallet(b: Booking) -> Optional[float]:
    if b.total_gross_weight_kg is None or not b.pallets or b.pallets <= 0:
        return None
    return b.total_gross_weight_kg / b.pallets


# ---- Ranking ---------------------------------------------------------------


def _minmax(values: list[float], higher_is_better: bool) -> list[float]:
    """Scale to 0..1 where 1 is best. All equal -> everyone gets 1."""
    lo, hi = min(values), max(values)
    if math.isclose(lo, hi):
        return [1.0] * len(values)
    return [((v - lo) if higher_is_better else (hi - v)) / (hi - lo) for v in values]


def _rank(eligible: list[CarrierResult], priority: str) -> list[CarrierResult]:
    """Best first, using the tie-breaks from the brief (then name, for a stable order)."""
    if priority == "Fastest":
        key = lambda r: (r.option.transit_days, r.total_cost, r.option.carrier)
    elif priority == "Most reliable":
        key = lambda r: (-r.option.on_time_rate, r.total_cost, r.option.carrier)
    elif priority == "Balanced":
        costs = _minmax([r.total_cost for r in eligible], higher_is_better=False)
        speed = _minmax([r.option.transit_days for r in eligible], higher_is_better=False)
        rel = _minmax([r.option.on_time_rate for r in eligible], higher_is_better=True)
        w = BALANCED_WEIGHTS
        for r, c, s, o in zip(eligible, costs, speed, rel):
            r.score = round(w["cost"] * c + w["speed"] * s + w["reliability"] * o, 3)
            r.reason = (f"Score {r.score:.2f} = 0.4×cost {c:.2f} + 0.3×speed {s:.2f} "
                        f"+ 0.3×reliability {o:.2f}")
        key = lambda r: (-r.score, r.total_cost, r.option.carrier)
    else:  # Cheapest
        key = lambda r: (r.total_cost, -r.option.on_time_rate, r.option.carrier)
    return sorted(eligible, key=key)


def _reason(win: CarrierResult, priority: str, pallets: float, n_eligible: int) -> str:
    c = win.option
    cost = f"{fmt.num(pallets)} pallet{'s' if pallets != 1 else ''} × {fmt.money(c.price_per_pallet)} = {fmt.money(win.total_cost)}"
    if n_eligible == 1:
        return f"{label(c)} is the only carrier on this route that can take these pallets: {cost}, " \
               f"{fmt.num(c.transit_days)} days, {fmt.num(c.on_time_rate)}% on time."
    if priority == "Fastest":
        return f"You asked for Fastest. {label(c)} is quickest at {fmt.num(c.transit_days)} days in transit " \
               f"({cost}, {fmt.num(c.on_time_rate)}% on time)."
    if priority == "Most reliable":
        return f"You asked for Most reliable. {label(c)} has the highest on-time rate, " \
               f"{fmt.num(c.on_time_rate)}% ({cost}, {fmt.num(c.transit_days)} days)."
    if priority == "Balanced":
        return f"You asked for Balanced, so each carrier is scored 0–1 on cost (40%), speed (30%) and " \
               f"reliability (30%). {label(c)} scores best at {win.score:.2f} ({cost}, " \
               f"{fmt.num(c.transit_days)} days, {fmt.num(c.on_time_rate)}% on time)."
    return f"You asked for Cheapest. {label(c)} is the lowest cost: {cost} " \
           f"({fmt.num(c.transit_days)} days, {fmt.num(c.on_time_rate)}% on time)."


def _headline(win: CarrierResult, priority: str, n_eligible: int, wpp: float) -> str:
    """The choice in one line: what makes it best for this priority, and that it can take the weight."""
    c = win.option
    fits = f"within its weight limit ({fmt.kg(wpp)} per pallet, max {fmt.kg(c.max_weight_per_pallet_kg)})"
    if n_eligible == 1:
        why = f"the only carrier that can take {fmt.kg(wpp)} per pallet"
        return f"{c.carrier}: {why} — {fmt.money(win.total_cost)}, {fmt.num(c.transit_days)} days."
    if priority == "Fastest":
        why = f"fastest at {fmt.num(c.transit_days)} days"
    elif priority == "Most reliable":
        why = f"most reliable at {fmt.num(c.on_time_rate)}% on time"
    elif priority == "Balanced":
        why = f"best balance of cost, speed and reliability (score {win.score:.2f})"
    else:
        why = f"lowest cost at {fmt.money(win.total_cost)}"
    return f"{c.carrier}: {why} and {fits}."


def _cap(s: str) -> str:
    return s[:1].upper() + s[1:]


def trade_off(win: CarrierResult, other: CarrierResult) -> str:
    """'£60.00 cheaper but 2 days slower than Carrier B (Express)'."""
    gains, losses = [], []
    dc = other.total_cost - win.total_cost
    if abs(dc) > 0.005:
        (gains if dc > 0 else losses).append(f"{fmt.money(abs(dc))} {'cheaper' if dc > 0 else 'more expensive'}")
    dt = other.option.transit_days - win.option.transit_days
    if dt:
        n = fmt.num(abs(dt))
        (gains if dt > 0 else losses).append(f"{n} day{'s' if abs(dt) != 1 else ''} {'faster' if dt > 0 else 'slower'}")
    dr = win.option.on_time_rate - other.option.on_time_rate
    if dr:
        (gains if dr > 0 else losses).append(
            f"{fmt.num(abs(dr))} points {'more' if dr > 0 else 'less'} reliable on time")
    vs = f"the runner-up, {label(other.option)}"
    if gains and losses:
        return f"{_cap(', '.join(gains))} but {' and '.join(losses)} than {vs}."
    if gains:
        return f"{_cap(', '.join(gains))} than {vs}, with no downside."
    if losses:
        return f"{_cap(', '.join(losses))} than {vs}, but it best matches your priority."
    return f"Same cost, speed and reliability as {vs}."


def recommend(b: Booking, carriers: list[CarrierOption]) -> Recommendation:
    priority = b.seller_priority or "Balanced"
    rec = Recommendation(priority=priority)
    route = [c for c in carriers
             if c.origin_country == b.origin_country and c.destination_country == b.destination_country]
    if not route:
        rec.reason = (f"No carrier in the rate card serves {b.origin_country or '?'} → "
                      f"{b.destination_country or '?'}." if b.destination_country
                      else "Choose a destination country to see carriers.")
        return rec

    wpp = weight_per_pallet(b)
    rec.weight_per_pallet = wpp
    if wpp is None or not float(b.pallets).is_integer():
        rec.all_options = [CarrierResult(option=c, status="Eligible",
                                         reason="Need pallets and gross weight to price this")
                           for c in route]
        rec.reason = "Add the number of pallets and the total gross weight to get a recommendation."
        return rec

    eligible, eliminated = [], []
    for c in route:
        r = CarrierResult(option=c, status="Eligible", total_cost=c.price_per_pallet * b.pallets)
        if c.max_weight_per_pallet_kg < wpp - 1e-9:
            r.status = "Eliminated"
            r.reason = (f"Max {fmt.kg(c.max_weight_per_pallet_kg)} per pallet; this booking has "
                        f"{fmt.kg(wpp)} per pallet")
            eliminated.append(r)
        else:
            eligible.append(r)

    if not eligible:
        best = max(c.max_weight_per_pallet_kg for c in route)
        need = math.ceil(b.total_gross_weight_kg / best - 1e-9)
        rec.reason = (f"No carrier on this route can take {fmt.kg(wpp)} per pallet (the highest limit is "
                      f"{fmt.kg(best)}). Use at least {need} pallets.")
        rec.all_options = eliminated
        return rec

    ranked = _rank(eligible, priority)
    ranked[0].status = "Recommended"
    rec.winner = ranked[0]
    if len(ranked) > 1:
        ranked[1].status = "Runner-up"
        rec.runner_up = ranked[1]
        rec.trade_off = trade_off(ranked[0], ranked[1])
    rec.reason = _reason(ranked[0], priority, b.pallets, len(ranked))
    rec.headline = _headline(ranked[0], priority, len(ranked), wpp)
    if not b.seller_priority:
        rec.reason = "No priority given, so Balanced is used. " + rec.reason
    rec.all_options = ranked + eliminated
    rec.ruled_out = _ruled_out(b, route, priority, ranked[0], wpp)
    return rec


def _ruled_out(b: Booking, route: list[CarrierOption], priority: str, win: CarrierResult, wpp: float) -> str:
    """If the weight limit (R-05) rules out the carrier this priority would pick, say so, and how many
    pallets would unlock it."""
    every = [CarrierResult(option=c, status="Eligible", total_cost=c.price_per_pallet * b.pallets) for c in route]
    ideal = _rank(every, priority)[0].option
    if ideal == win.option:
        return ""
    need = math.ceil(b.total_gross_weight_kg / ideal.max_weight_per_pallet_kg - 1e-9)
    return (f"R-05 rules out {label(ideal)}, the {priority} pick: {fmt.kg(wpp)} per pallet is over its "
            f"{fmt.kg(ideal.max_weight_per_pallet_kg)} max, so {win.option.carrier} is recommended instead. "
            f"To use {ideal.carrier}, spread the goods over {need} pallets ({fmt.kg(b.total_gross_weight_kg / need)} "
            f"each): {need} × {fmt.money(ideal.price_per_pallet)} = {fmt.money(need * ideal.price_per_pallet)}, "
            f"{fmt.num(ideal.transit_days)} days, {fmt.num(ideal.on_time_rate)}% on time.")

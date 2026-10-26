"""Diagnosis: which number is most likely wrong, and which issues share one root cause.

For a failed check there are usually several numbers that could be the typo
(e.g. R-03: cartons, quantity or units per carton). Each candidate fix is tried
on a copy of the booking and scored by how well it agrees with the OTHER numbers:
declared value (R-02), booking carton total (R-04), and gross weight (R-07).
The best-supported candidate becomes the suggestion, with a confidence level and
the evidence in plain English. All deterministic code.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field

from core import fmt, rules
from core.models import Booking, Issue, Item


class RootCause(BaseModel):
    title: str                       # "Most likely typo: cartons for MUG-01 should be 90, not 80"
    explanation: str                 # "because …"
    confidence: str                  # High / Medium / Low
    fixes: list[str] = Field(default_factory=list)    # issue keys this one change resolves
    fix_action: Optional[dict] = None
    fix_label: str = "Apply fix"


def issue_key(i: Issue) -> str:
    return f"{i.rule_id}:{i.item_sku or ''}"


# ---- helpers -----------------------------------------------------------------


def _with(b: Booking, action: dict) -> Booking:
    sim = b.model_copy(deep=True)
    apply_fix(sim, action)
    return sim


def _passes(rule, b: Booking, sku: Optional[str] = None) -> bool:
    issues = rule(b)
    return not [i for i in issues if sku is None or i.item_sku == sku]


def _plausible_packaging(b: Booking) -> Optional[bool]:
    """Gross weight should be the goods plus a little packaging (ratio 1.0-1.6)."""
    goods = rules.goods_weight(b)
    if not goods or b.total_gross_weight_kg is None:
        return None
    return 1.0 <= b.total_gross_weight_kg / goods <= 1.6


def looks_like_typo(a: float, b: float) -> Optional[str]:
    """Swapped digits, one wrong digit, or a factor of 10."""
    if a <= 0 or b <= 0:
        return None
    for r in (10, 100):
        if abs(a * r - b) < 1e-6 or abs(b * r - a) < 1e-6:
            return "an extra or missing zero"
    sa, sb = fmt.num(a).replace(",", ""), fmt.num(b).replace(",", "")
    if len(sa) == len(sb):
        if sorted(sa) == sorted(sb) and sum(x != y for x, y in zip(sa, sb)) == 2:
            return "two swapped digits"
        if sum(x != y for x, y in zip(sa, sb)) == 1:
            return "one mistyped digit"
    return None


def _confidence(best: float, second: float) -> str:
    if best >= 3 and best - second >= 2:
        return "High"
    if best >= 2 or best - second >= 1.5:
        return "Medium"
    return "Low"


def _resolved(b: Booking, sim: Booking, sku: str) -> list[str]:
    """Issue keys that fail on b but pass on sim."""
    out = []
    checks = [("R-02", rules.r02_declared_value, None), ("R-03", rules.r03_carton_maths, sku),
              ("R-04", rules.r04_total_cartons, None), ("R-07", rules.r07_gross_weight, None)]
    for rid, fn, s in checks:
        if not _passes(fn, b, s) and _passes(fn, sim, s):
            out.append(f"{rid}:{s or ''}")
    return out


# ---- R-03: which of quantity / cartons / units per carton is wrong --------------


def _diag_r03(b: Booking, it: Item) -> Optional[RootCause]:
    q, u, c = it.quantity, it.units_per_carton, it.cartons
    name = it.sku or it.description or "item"
    cands = []    # (field, new value, old value)
    if u and (q / u).is_integer():
        cands.append(("cartons", q / u, c))
    cands.append(("quantity", u * c, q))
    if c and (q / c).is_integer() and q / c != u:
        cands.append(("units_per_carton", q / c, u))

    r02_now = _passes(rules.r02_declared_value, b) if rules.items_value(b) is not None and \
        b.total_declared_value is not None else None
    r04_now = _passes(rules.r04_total_cartons, b) if b.cartons is not None else None
    scored = []
    for f, new, old in cands:
        action = {"target": "item", "sku": it.sku, "field": f, "value": new}
        sim = _with(b, action)
        score, why = {"cartons": 0.5, "quantity": 0.0, "units_per_carton": -0.5}[f], []
        # Declared value (R-02)
        if r02_now is not None:
            r02_sim = _passes(rules.r02_declared_value, sim)
            if f == "quantity":
                if r02_sim and not r02_now:
                    score += 3
                    why.append(f"with {fmt.num(new)} units the declared value {fmt.money(b.total_declared_value)} "
                               f"matches the items exactly")
                elif r02_now and not r02_sim:
                    score -= 2
            elif r02_now:
                score += 2
                why.append(f"the declared value {fmt.money(b.total_declared_value)} matches quantity "
                           f"{fmt.num(q)} × {fmt.money(it.unit_price)}, so the quantity looks right")
        # Booking carton total (R-04)
        if r04_now is not None:
            r04_sim = _passes(rules.r04_total_cartons, sim)
            if f == "cartons":
                if r04_sim and not r04_now:
                    score += 2
                    why.append(f"the booking's total of {fmt.num(b.cartons)} cartons also expects {fmt.num(new)} here")
                elif r04_now and not r04_sim:
                    score -= 2
            elif r04_now:
                score += 1.5
                why.append(f"{fmt.num(c)} cartons agrees with the booking's carton total")
        # Gross weight plausibility (R-07)
        p_now, p_sim = _plausible_packaging(b), _plausible_packaging(sim)
        if p_sim is not None and p_now != p_sim:
            score += 1 if p_sim else -1
            if p_sim:
                why.append(f"the gross weight {fmt.kg(b.total_gross_weight_kg)} fits {fmt.num(new)} units "
                           f"better (goods {fmt.kg(rules.goods_weight(sim))})")
        if f == "cartons":
            why.append(f"{fmt.num(q)} ÷ {fmt.num(u)} per carton = {fmt.num(new)} exactly")
        typo = looks_like_typo(old, new)
        if typo:
            score += 0.5
            why.append(f"{fmt.num(old)} vs {fmt.num(new)} looks like {typo}")
        scored.append((score, f, new, old, why, action, sim))

    scored.sort(key=lambda s: -s[0])
    best = scored[0]
    second = scored[1][0] if len(scored) > 1 else -1
    score, f, new, old, why, action, sim = best
    label = {"cartons": "cartons", "quantity": "quantity", "units_per_carton": "units per carton"}[f]
    alt = ""
    if len(scored) > 1 and second > score - 1.5:
        s2 = scored[1]
        alt = f" Less likely: {s2[1].replace('_', ' ')} should be {fmt.num(s2[2])}."
    return RootCause(
        title=f"Most likely typo: {label} for {name} should be {fmt.num(new)}, not {fmt.num(old)}",
        explanation="Because " + "; ".join(why) + "." + alt,
        confidence=_confidence(score, second),
        fixes=sorted({f"R-03:{it.sku or ''}", *_resolved(b, sim, it.sku)}),
        fix_action=action, fix_label=f"Set {label} for {name} to {fmt.num(new)}")


# ---- R-02: which item (or the total) explains the value gap ----------------------


def _diag_r02(b: Booking) -> Optional[RootCause]:
    computed, declared = rules.items_value(b), b.total_declared_value
    if computed is None or declared is None:
        return None
    packing_ok = _passes(rules.r03_carton_maths, b)
    cands = []
    # Candidate: the declared total is the wrong number. It is worked out from the items, so it is
    # the safest number to correct; changing a unit price changes what the buyer pays.
    why, score = ["the declared value is a total worked out from the items, so it is the safest number to "
                  "correct"], 1.0
    if packing_ok:
        score += 1.5
        why.append("every item's packing maths (units per carton × cartons) adds up, so the quantities look right")
    typo = looks_like_typo(declared, round(computed, 2))
    if typo:
        score += 2
        why.append(f"{fmt.money(declared)} vs {fmt.money(computed)} looks like {typo}")
    cands.append((score, f"Most likely the declared value is wrong: it should be {fmt.money(computed)}, "
                         f"not {fmt.money(declared)}", why,
                  {"target": "booking", "field": "total_declared_value", "value": round(computed, 2)},
                  f"Set declared value to {fmt.money(computed)}"))
    # Candidate: one item's price or quantity is wrong
    for it in b.items:
        others = computed - it.quantity * it.unit_price
        name = it.sku or it.description or "item"
        if it.quantity:
            p2 = (declared - others) / it.quantity
            if p2 > 0 and abs(round(p2, 2) - p2) < 1e-9 and abs(p2 - it.unit_price) > 1e-9:
                s, w = 0.5, [f"a unit price of {fmt.money(p2)} for {name} would make the totals match exactly"]
                if round(p2 * 100) % 50 == 0 or round(p2 * 100) % 100 in (95, 99):
                    s += 1
                    w.append(f"{fmt.money(p2)} is a typical price point")
                # any two single-digit prices differ by "one digit", so that is no evidence of a typo
                t = looks_like_typo(it.unit_price, p2) if max(it.unit_price, p2) >= 10 else None
                if t:
                    s += 1.5
                    w.append(f"{fmt.money(it.unit_price)} vs {fmt.money(p2)} looks like {t}")
                cands.append((s, f"Most likely typo: unit price for {name} should be {fmt.money(p2)}, "
                                 f"not {fmt.money(it.unit_price)}", w,
                              {"target": "item", "sku": it.sku, "field": "unit_price", "value": round(p2, 2)},
                              f"Set unit price for {name} to {fmt.money(p2)}"))
        if it.unit_price:
            q2 = (declared - others) / it.unit_price
            if q2 > 0 and abs(q2 - round(q2)) < 1e-9 and q2 != it.quantity:
                s, w = 0.0, [f"a quantity of {fmt.num(q2)} for {name} would make the totals match exactly"]
                if it.units_per_carton and it.cartons and it.units_per_carton * it.cartons == q2:
                    s += 3
                    w.append(f"and {fmt.num(q2)} = {fmt.num(it.units_per_carton)} per carton × {fmt.num(it.cartons)} cartons")
                elif packing_ok:
                    s -= 1
                cands.append((s, f"Most likely typo: quantity for {name} should be {fmt.num(q2)}, "
                                 f"not {fmt.num(it.quantity)}", w,
                              {"target": "item", "sku": it.sku, "field": "quantity", "value": q2},
                              f"Set quantity for {name} to {fmt.num(q2)}"))
    cands.sort(key=lambda c: -c[0])
    score, title, why, action, label = cands[0]
    second = cands[1][0] if len(cands) > 1 else -1
    alt = ""
    if len(cands) > 1 and second > score - 1.5:
        alt_title = cands[1][1].replace("Most likely typo: ", "").replace("Most likely the ", "the ")
        alt = f" Also possible: {alt_title}."
    gap = f"The gap is {fmt.money(abs(declared - computed))}. "
    return RootCause(title=title, explanation=gap + "Because " + "; ".join(why or ["it is the simplest single change"])
                     + "." + alt, confidence=_confidence(score, second),
                     fixes=sorted({"R-02:", *_resolved(b, _with(b, action), action.get("sku"))}),
                     fix_action=action, fix_label=label)


# ---- R-04: is it the booking total or an item? -------------------------------------


def _diag_r04(b: Booking) -> Optional[RootCause]:
    if b.cartons is None or not b.items or any(it.cartons is None for it in b.items):
        return None
    total = sum(it.cartons for it in b.items)
    packing_ok = _passes(rules.r03_carton_maths, b)
    why = []
    score = 1.0
    if packing_ok:
        score += 2
        why.append("every item's cartons match its quantity ÷ units per carton, so the item counts look right")
    typo = looks_like_typo(b.cartons, total)
    if typo:
        score += 1
        why.append(f"{fmt.num(b.cartons)} vs {fmt.num(total)} looks like {typo}")
    action = {"target": "booking", "field": "cartons", "value": total}
    return RootCause(title=f"Most likely the booking's carton total is wrong: it should be {fmt.num(total)}, "
                           f"not {fmt.num(b.cartons)}",
                     explanation="Because " + "; ".join(why or ["the items add up to a different total"]) + ".",
                     confidence=_confidence(score, 0), fixes=["R-04:"], fix_action=action,
                     fix_label=f"Set total cartons to {fmt.num(total)}")


# ---- R-07: is the gross weight wrong, or an item's unit weight? -------------------

EMPTY_PALLET_KG = 25    # typical empty wooden pallet (EUR/UK standard pallets weigh ~20-25 kg)


def _diag_r07(b: Booking) -> Optional[RootCause]:
    goods, gross = rules.goods_weight(b), b.total_gross_weight_kg
    if goods is None or gross is None:
        return None
    # A low gross weight is fixed by re-weighing, never by shrinking a product's weight:
    # a seller's unit weight is a fact about the product, and a smaller one hides the problem.
    cands = []
    # Candidate: the gross weight itself is too low -> estimate it
    pallets = int(b.pallets) if b.pallets and b.pallets > 0 else 0
    estimate = round(goods + EMPTY_PALLET_KG * pallets)
    why = [f"the goods alone weigh {fmt.kg(goods)}, so {fmt.kg(gross)} can't include them, the cartons and the pallets"]
    score = 1.5
    if _passes(rules.r03_carton_maths, b) and _passes(rules.r02_declared_value, b):
        score += 1
        why.append("the item quantities agree with the packing and the declared value, so the quantities look right")
    typo = looks_like_typo(gross, estimate)
    if typo:
        why.append(f"{fmt.kg(gross)} vs about {fmt.kg(estimate)} may be {typo}")
    est_txt = (f"{fmt.kg(goods)} goods + {pallets} × {EMPTY_PALLET_KG} kg empty pallets" if pallets
               else f"{fmt.kg(goods)} goods")
    cands.append((score, f"Most likely the gross weight is too low: raise it to at least {fmt.kg(estimate)} "
                         f"plus packaging, not {fmt.kg(gross)}", why,
                  {"target": "booking", "field": "total_gross_weight_kg", "value": float(estimate),
                   "label": "estimate"},
                  f"Use estimated gross weight {fmt.kg(estimate)} (re-weigh to confirm)"))
    cands.sort(key=lambda c: -c[0])
    score, title, why, action, label = cands[0]
    second = cands[1][0] if len(cands) > 1 else -1
    note = ""
    if action["field"] == "total_gross_weight_kg":
        note = (f" The estimate is {est_txt} (cartons not included), so treat it as a minimum and "
                "re-weigh the shipment before collection.")
    return RootCause(title=title, explanation="Because " + "; ".join(why) + "." + note,
                     confidence=_confidence(score, second), fixes=["R-07:"], fix_action=action, fix_label=label)


# ---- Public API ----------------------------------------------------------------------


def diagnose(b: Booking, issues: list[Issue]) -> tuple[list[RootCause], list[Issue]]:
    """Return (root causes, issues not explained by any root cause)."""
    keys = {issue_key(i) for i in issues}
    roots: list[RootCause] = []
    covered: set[str] = set()
    for it in b.items:
        k = f"R-03:{it.sku or ''}"
        if k in keys and None not in (it.quantity, it.units_per_carton, it.cartons):
            rc = _diag_r03(b, it)
            if rc:
                rc.fixes = [f for f in rc.fixes if f in keys]
                roots.append(rc)
                covered |= set(rc.fixes)
    # Totals are judged against the booking AFTER the per-item fixes above, so the
    # suggested declared value / carton total agrees with those fixes.
    after = b.model_copy(deep=True)
    for rc in roots:
        apply_fix(after, rc.fix_action)
    note = " (after the item fix above)" if roots else ""
    for rule_key, diag in (("R-02:", _diag_r02), ("R-04:", _diag_r04), ("R-07:", _diag_r07)):
        if rule_key in keys and rule_key not in covered:
            rc = diag(after)
            if rc:
                rc.fixes = [f for f in rc.fixes if f in keys]
                rc.title += note
                roots.append(rc)
                covered |= set(rc.fixes)
    roots.sort(key=lambda r: -len(r.fixes))
    return roots, [i for i in issues if issue_key(i) not in covered]


def clear_data_issues(b: Booking, field: str, sku: Optional[str] = None):
    """Drop the loader's DATA issues about a field once it has been set (e.g. a misspelt country fixed)."""
    b.data_issues = [i for i in b.data_issues if not (i.field == field and i.item_sku == sku)]


def apply_fix(b: Booking, action: dict) -> str:
    """Apply a fix_action to the booking in place. Returns 'cartons for MUG-01: 80 → 90'."""
    f, value = action["field"], action["value"]
    if f == "ready_date" and isinstance(value, str):
        value = date.fromisoformat(value)
    if action["target"] == "booking":
        obj, where = b, ""
    else:
        obj = next((it for it in b.items if it.sku == action.get("sku")), None)
        if obj is None:
            return "Item not found — nothing changed."
        where = f" for {obj.sku}"
    old = getattr(obj, f)
    setattr(obj, f, value)
    clear_data_issues(b, f, action.get("sku") if action["target"] == "item" else None)
    if f == "hs_code":
        obj.hs_possible_leading_zero_lost = False
    show = lambda v: fmt.money(v) if f in ("total_declared_value", "unit_price") else (
        fmt.d(v) if f == "ready_date" else ("Yes" if v is True else "No" if v is False else
                                            fmt.num(v) if isinstance(v, float) else str(v)))
    names = {"total_gross_weight_kg": "gross weight", "total_declared_value": "declared value",
             "unit_weight_kg": "unit weight", "hs_code": "HS code", "delivery_appointment_booked": "delivery slot booked"}
    if f in ("total_gross_weight_kg", "unit_weight_kg"):
        show = lambda v: fmt.kg(v)
    return f"{names.get(f, f.replace('_', ' '))}{where}: {show(old) if old is not None else '—'} → {show(value)}"


# ---- Fix all ---------------------------------------------------------------------------


def high_confidence_actions(b: Booking, issues: list[Issue]) -> list[tuple[RootCause, dict]]:
    """Fixes safe to apply without asking: High-confidence root causes, plus issues whose own fix is
    certain (a misspelt choice, an HS code that lost its leading zero in Excel).

    Totals (declared value, carton total, gross weight) are diagnosed as if the item fixes
    were already made, so a High total fix is only safe when every item fix in the booking
    is High too (and therefore applied alongside it)."""
    roots, _ = diagnose(b, issues)
    item_roots = [r for r in roots if r.fix_action and r.fix_action["target"] == "item"
                  and r.fix_action["field"] in ("cartons", "quantity", "units_per_carton")]
    items_all_high = all(r.confidence == "High" for r in item_roots)
    out = []
    for r in roots:
        if r.confidence != "High" or not r.fix_action:
            continue
        if r not in item_roots and item_roots and not items_all_high:
            continue
        out.append((r, r.fix_action))
    # sure corrections the rules/loader flag themselves: misspellings, an Excel-dropped HS zero
    out += [(i, i.fix_action) for i in issues if i.fix_action and i.fix_action.get("certain")
            and all(i.fix_action != a for _, a in out)]
    return out


def fix_all(bookings: list[Booking], evaluate_fn) -> dict[str, list[str]]:
    """Apply every high-confidence fix, re-checking after each round (a fix can reveal the next).
    Returns {booking_id: ["cartons for MUG-01: 80 → 90", ...]} for bookings that changed."""
    changes: dict[str, list[str]] = {}
    for b in bookings:
        for _ in range(3):
            actions = high_confidence_actions(b, evaluate_fn(b).issues)
            if not actions:
                break
            for _, action in actions:
                changes.setdefault(b.booking_id or "?", []).append(apply_fix(b, action))
    return changes

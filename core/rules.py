"""Rulebook R-01..R-10 as pure functions. Code decides pass/fail, never the LLM.

Each check takes a Booking (plus carriers / today where needed) and returns a
list of Issues; an empty list means the rule passes. If a value a rule needs
is missing, the rule is skipped for that value: the loader / chat already
reports the missing value as a DATA issue, so we don't double-report.
"""
from __future__ import annotations

import math
import re
from datetime import date
from typing import Optional

from core import fmt
from core.dangerous_goods import detect
from core.models import Booking, CarrierOption, Issue, Item, ITEM_ORIGIN_COUNTRIES

CUSTOMS_HOLD = ("Customs may hold the shipment (a customs hold = customs stops the goods "
                "until the paperwork is corrected), so the stock sits at the border.")
WHY = {
    "R-01": "Customs uses the HS code (the international code that classifies a product) to "
            "decide duties and checks. " + CUSTOMS_HOLD,
    "R-02": "The declared value goes on the commercial invoice and decides duty and VAT. "
            "If it doesn't match the items, " + CUSTOMS_HOLD[0].lower() + CUSTOMS_HOLD[1:],
    "R-03": "The receiving warehouse counts cartons and units on arrival; if the numbers don't "
            "add up it will report units as missing and the shipment gets stuck in a dispute.",
    "R-04": "The receiving warehouse checks the carton count on the booking; a mismatch means "
            "cartons are reported as missing or the delivery is refused.",
    "R-05": "Every carrier has a maximum weight per pallet. Overweight pallets are rejected or "
            "re-weighed, causing delay and extra charges.",
    "R-06": "Lithium batteries, aerosols and flammable liquids are dangerous goods. They need "
            "special packing and paperwork; undeclared, the carrier refuses them and " +
            CUSTOMS_HOLD[0].lower() + CUSTOMS_HOLD[1:],
    "R-07": "The declared gross weight is lighter than the goods themselves, which is impossible. "
            "The carrier will almost certainly re-weigh it and may charge extra or delay it.",
    "R-08": "Warehouses only accept deliveries in a booked time slot; without one the driver "
            "may be turned away and the delivery rebooked at extra cost.",
    "R-09": "Country of origin (where the product was made, not where it ships from) decides "
            "duty rates. " + CUSTOMS_HOLD,
    "R-10": "The collection date has already passed, so the carrier can't collect on that day.",
}
TITLES = {
    "R-01": "HS code missing or too short", "R-02": "Declared value doesn't match items",
    "R-03": "Units per carton × cartons ≠ quantity", "R-04": "Booking cartons ≠ item cartons",
    "R-05": "Pallets too heavy for carrier", "R-06": "Possible dangerous goods",
    "R-07": "Gross weight lighter than the goods", "R-08": "No delivery appointment at warehouse",
    "R-09": "Country of origin missing", "R-10": "Ready date is in the past",
}
# Neutral names, for "Passed: ..." lists.
RULE_NAMES = {
    "R-01": "HS codes", "R-02": "Declared value", "R-03": "Carton maths per item",
    "R-04": "Total cartons", "R-05": "Pallet weight", "R-06": "Dangerous goods",
    "R-07": "Gross weight", "R-08": "Delivery appointment", "R-09": "Country of origin",
    "R-10": "Ready date",
}
SEVERITY = {"R-01": "Red", "R-02": "Red", "R-03": "Red", "R-04": "Red", "R-05": "Red",
            "R-06": "Red", "R-07": "Amber", "R-08": "Amber", "R-09": "Amber", "R-10": "Amber"}


def _issue(rule: str, b: Booking, explanation: str, fix: str, sku: Optional[str] = None,
           title: Optional[str] = None, fix_action: Optional[dict] = None) -> Issue:
    return Issue(rule_id=rule, severity=SEVERITY[rule], title=title or TITLES[rule],
                 explanation=explanation, why_it_matters=WHY[rule], fix=fix, item_sku=sku,
                 booking_id=b.booking_id, fix_action=fix_action)


def _name(it: Item) -> str:
    return it.sku or (f"Items row {it.source_row}" if it.source_row else "item")


def _all_known(items: list[Item], *fields: str) -> bool:
    return bool(items) and all(getattr(it, f) is not None for it in items for f in fields)


# ---- Rules -----------------------------------------------------------------


BOUNDARY = chr(92) + "b"          # regex word boundary

# HS chapters 01-09 are the only ones that start with 0, so Excel can only drop a leading zero from
# these. Suggest the zero only when the product plausibly belongs to that chapter.
ZERO_CHAPTERS = {
    "01": ("live animals", "live animal|horse|cattle|cow|sheep|goat|pig|chicken|poultry"),
    "02": ("meat", "meat|beef|pork|lamb|mutton|venison|veal"),
    "03": ("fish and seafood", "fish|salmon|tuna|cod|prawn|shrimp|crab|lobster|seafood|mussel|oyster"),
    "04": ("dairy, eggs and honey", "milk|cream|butter|cheese|yogh?urt|egg|honey|dairy"),
    "05": ("other animal products", "feather|bone|horn|animal hair"),
    "06": ("plants and flowers", "plant|flower|bulb|tree|bouquet|foliage|seedling"),
    "07": ("vegetables", "vegetable|potato|tomato|onion|garlic|carrot|lettuce|cabbage|bean|pea|lentil|mushroom"),
    "08": ("fruit and nuts", "fruit|nut|apple|banana|orange|lemon|grape|berry|berries|almond|cashew|walnut|"
                             "date|fig|coconut|mango"),
    "09": ("coffee, tea and spices", "coffee|tea|spice|pepper|vanilla|cinnamon|clove|nutmeg|ginger|turmeric|"
                                     "saffron|cardamom|cumin"),
}


# Words that make it equipment, a container or a processed product, not the raw goods (a coffee mug is chapter 69)
NOT_RAW_GOODS = ("mug|cup|maker|machine|grinder|kettle|press|filter|spoon|bowl|plate|glass|vase|jar|pot|"
                 "candle|soap|print|poster|book|card|toy|cable|case|juice|jam|sauce|perfume|scent")


def zero_chapter(digits: str, description: Optional[str]) -> Optional[str]:
    """The chapter name if '0' + digits fits the product (e.g. 90121 + 'coffee beans' -> coffee...)."""
    chapter = ZERO_CHAPTERS.get("0" + digits[:1])
    text = (description or "").lower()
    if re.search(BOUNDARY + "(" + NOT_RAW_GOODS + ")s?" + BOUNDARY, text):
        return None
    if chapter and re.search(r"\b(" + chapter[1] + r")s?\b", (description or "").lower()):
        return chapter[0]
    return None


def r01_hs_code(b: Booking) -> list[Issue]:
    out = []
    for it in b.items:
        digits = re.sub(r"\D", "", it.hs_code or "")
        if not digits:
            out.append(_issue("R-01", b, f"{_name(it)} ({it.description or 'no description'}) has no HS code.",
                              f"Look up the HS code for '{it.description or _name(it)}' on the UK Trade "
                              "Tariff (gov.uk/trade-tariff) and enter at least the first 6 digits.",
                              it.sku))
        elif len(digits) < 6:
            fix = (f"Enter the full HS code (at least 6 digits) for '{it.description or _name(it)}'; "
                   "check it on the UK Trade Tariff (gov.uk/trade-tariff).")
            action, likely = None, ""
            chapter = zero_chapter(digits, it.description) if len(digits) == 5 else None
            if chapter and it.hs_possible_leading_zero_lost:
                likely = f" It is almost certainly 0{digits}: Excel drops the leading zero from numbers."
                fix = (f"Set it to 0{digits} — chapter 0{digits[0]} is {chapter}, which fits "
                       f"'{it.description}'. Tap the fix, or re-enter the code in Excel as text so the zero stays.")
                action = {"target": "item", "sku": it.sku, "field": "hs_code", "value": "0" + digits,
                          "label": f"Set HS code to 0{digits}"}
            out.append(_issue("R-01", b, f"{_name(it)} has HS code '{it.hs_code}' with only "
                                         f"{len(digits)} digits; at least 6 are needed.{likely}",
                              fix, it.sku, fix_action=action))
    return out


def items_value(b: Booking) -> Optional[float]:
    if not _all_known(b.items, "quantity", "unit_price"):
        return None
    return sum(it.quantity * it.unit_price for it in b.items)


def r02_declared_value(b: Booking) -> list[Issue]:
    computed = items_value(b)
    declared = b.total_declared_value
    if computed is None or declared is None:
        return []
    diff = declared - computed
    tolerance = 0.01 * computed
    if abs(diff) <= tolerance + 1e-9:
        return []
    pct = abs(diff) / computed * 100 if computed else float("inf")
    breakdown = " + ".join(f"{fmt.num(it.quantity)} × {fmt.money(it.unit_price)}" for it in b.items[:4])
    if len(b.items) > 4:
        breakdown += " + …"
    pct_txt = f"{pct:.1f}%" if math.isfinite(pct) else "n/a"
    return [_issue("R-02", b,
                   f"Declared value {fmt.money(declared)} but items add up to {fmt.money(computed)} "
                   f"({breakdown}). Difference {fmt.money(abs(diff))} ({pct_txt} of the items total; "
                   f"allowed 1% = {fmt.money(tolerance)}).",
                   f"If the item quantities and prices are right, change the declared value to "
                   f"{fmt.money(computed)}. Otherwise correct the item line that is wrong.",
                   fix_action={"target": "booking", "field": "total_declared_value",
                               "value": round(computed, 2)})]


def r03_carton_maths(b: Booking) -> list[Issue]:
    out = []
    for it in b.items:
        if None in (it.units_per_carton, it.cartons, it.quantity):
            continue
        packed = it.units_per_carton * it.cartons
        if abs(packed - it.quantity) < 1e-9:
            continue
        fix = "Recount and correct either units per carton, cartons, or quantity."
        action = None
        if it.units_per_carton and (it.quantity / it.units_per_carton).is_integer():
            right = it.quantity / it.units_per_carton
            fix = (f"If quantity {fmt.num(it.quantity)} is right, cartons should be "
                   f"{fmt.num(right)} ({fmt.num(it.quantity)} ÷ {fmt.num(it.units_per_carton)}). "
                   f"Otherwise correct the quantity to {fmt.num(packed)}.")
            action = {"target": "item", "sku": it.sku, "field": "cartons", "value": right}
        out.append(_issue("R-03", b,
                          f"{_name(it)}: {fmt.num(it.units_per_carton)} units per carton × "
                          f"{fmt.num(it.cartons)} cartons = {fmt.num(packed)} units, but quantity is "
                          f"{fmt.num(it.quantity)} (difference {fmt.num(abs(packed - it.quantity))}).",
                          fix, it.sku, fix_action=action))
    return out


def r04_total_cartons(b: Booking) -> list[Issue]:
    if b.cartons is None or not _all_known(b.items, "cartons"):
        return []
    total = sum(it.cartons for it in b.items)
    if abs(total - b.cartons) < 1e-9:
        return []
    parts = " + ".join(f"{_name(it)} {fmt.num(it.cartons)}" for it in b.items[:5])
    return [_issue("R-04", b,
                   f"Booking says {fmt.num(b.cartons)} cartons but the items add up to {fmt.num(total)} "
                   f"({parts}). Difference {fmt.num(abs(total - b.cartons))}.",
                   f"If the item carton counts are right, change the booking's total cartons to "
                   f"{fmt.num(total)}. Otherwise correct the item carton count that is wrong.",
                   fix_action={"target": "booking", "field": "cartons", "value": total})]


def route_carriers(b: Booking, carriers: list[CarrierOption]) -> list[CarrierOption]:
    return [c for c in carriers
            if c.origin_country == b.origin_country and c.destination_country == b.destination_country]


def r05_pallet_weight(b: Booking, carriers: list[CarrierOption],
                      chosen: Optional[CarrierOption] = None) -> list[Issue]:
    """chosen = the recommended carrier. If None, the heaviest-capacity carrier on the
    route is used (the recommendation only ever picks a carrier that can take the weight,
    so R-05 fails exactly when no carrier on the route can)."""
    if b.total_gross_weight_kg is None or b.pallets is None or b.destination_country is None:
        return []
    if b.pallets <= 0 or not float(b.pallets).is_integer():
        return [_issue("R-05", b,
                       f"Pallets is {fmt.num(b.pallets)}, so weight per pallet can't be worked out "
                       f"(total gross weight {fmt.kg(b.total_gross_weight_kg)}).",
                       "Enter the number of pallets as a whole number of 1 or more.",
                       title="Pallet count is not valid")]
    wpp = b.total_gross_weight_kg / b.pallets
    options = route_carriers(b, carriers)
    if not options:
        return [_issue("R-05", b, f"No carrier in the rate card serves {b.origin_country} → "
                                  f"{b.destination_country}, so pallet weight can't be checked.",
                       "Check the destination country.", title="No carrier serves this route")]
    target = chosen or max(options, key=lambda c: c.max_weight_per_pallet_kg)
    if wpp <= target.max_weight_per_pallet_kg + 1e-9:
        return []
    best = max(c.max_weight_per_pallet_kg for c in options)
    need = math.ceil(b.total_gross_weight_kg / best - 1e-9)
    who = (f"{target.carrier} ({target.service}) accepts" if chosen
           else f"the highest limit of any carrier on this route is")
    return [_issue("R-05", b,
                   f"{fmt.kg(b.total_gross_weight_kg)} ÷ {fmt.num(b.pallets)} pallets = {fmt.kg(wpp)} per "
                   f"pallet, but {who} {fmt.kg(target.max_weight_per_pallet_kg)} per pallet.",
                   f"Spread the goods over at least {need} pallets ({fmt.kg(b.total_gross_weight_kg)} ÷ "
                   f"{fmt.kg(best)} = {b.total_gross_weight_kg / best:.2f}, rounded up), "
                   f"giving {fmt.kg(b.total_gross_weight_kg / need)} per pallet.",
                   fix_action={"target": "booking", "field": "pallets", "value": need})]


def r06_dangerous_goods(b: Booking) -> list[Issue]:
    out = []
    for it in b.items:
        signals = detect(it.description, it.sku, it.hs_code)
        if signals:
            found = " ".join(signals).lower()
            # an example of "not actually dangerous" that fits what was detected
            example = ("e.g. a pump spray, not a pressurised aerosol can" if "aerosol" in found else
                       "e.g. alcohol-free or water-based" if "flammable" in found else
                       "e.g. no battery inside")
            out.append(_issue("R-06", b,
                              f"{_name(it)} ({it.description or 'no description'}) looks like dangerous "
                              f"goods: {'; '.join(signals)}.",
                              f"Remove {_name(it)} from this shipment, or if it is not actually dangerous "
                              f"({example}), make the description say so clearly. Dangerous "
                              "goods need a specialist dangerous-goods service, not this booking.",
                              it.sku))
    return out


def goods_weight(b: Booking) -> Optional[float]:
    if not _all_known(b.items, "unit_weight_kg", "quantity"):
        return None
    return sum(it.unit_weight_kg * it.quantity for it in b.items)


def r07_gross_weight(b: Booking) -> list[Issue]:
    goods = goods_weight(b)
    if goods is None or b.total_gross_weight_kg is None:
        return []
    if b.total_gross_weight_kg + 1e-9 >= goods:
        return []
    parts = " + ".join(f"{fmt.num(it.quantity)} × {fmt.kg(it.unit_weight_kg)}" for it in b.items[:4])
    return [_issue("R-07", b,
                   f"Total gross weight is {fmt.kg(b.total_gross_weight_kg)}, but the goods alone weigh "
                   f"{fmt.kg(goods)} ({parts}{' + …' if len(b.items) > 4 else ''}). "
                   f"Short by {fmt.kg(goods - b.total_gross_weight_kg)}.",
                   f"Re-weigh the shipment. Gross weight includes goods, cartons and pallets, so it must "
                   f"be at least {fmt.kg(goods)}; also check each item's unit weight and quantity.")]


def r08_delivery_appointment(b: Booking) -> list[Issue]:
    if b.destination_type != "Warehouse" or b.delivery_appointment_booked is True:
        return []
    state = "not booked" if b.delivery_appointment_booked is False else "not stated"
    return [_issue("R-08", b,
                   f"Destination is a warehouse in {b.destination_city or '?'} but the delivery "
                   f"appointment is {state}.",
                   "Book a delivery slot (a time window at the receiving warehouse) before collection, "
                   "then set 'Delivery appointment booked' to Yes.",
                   fix_action={"target": "booking", "field": "delivery_appointment_booked",
                               "value": True, "label": "Mark slot as booked"})]


def r09_country_of_origin(b: Booking) -> list[Issue]:
    return [_issue("R-09", b, f"{_name(it)} ({it.description or 'no description'}) has no country "
                              "of origin.",
                   f"Enter where {_name(it)} was made (not where it ships from): "
                   f"{', '.join(ITEM_ORIGIN_COUNTRIES)}.", it.sku)
            for it in b.items if not (it.country_of_origin or "").strip()]


def r10_ready_date(b: Booking, today: Optional[date] = None) -> list[Issue]:
    today = today or date.today()
    if b.ready_date is None or b.ready_date >= today:
        return []
    days = (today - b.ready_date).days
    return [_issue("R-10", b,
                   f"Ready to ship date {fmt.d(b.ready_date)} is {days} day{'s' if days != 1 else ''} "
                   f"before today ({fmt.d(today)}).",
                   f"Change the ready date to today ({fmt.d(today)}) or a later date when the goods "
                   "will actually be packed.",
                   fix_action={"target": "booking", "field": "ready_date", "value": today.isoformat()})]


# ---- Run everything --------------------------------------------------------


def _checkable(b: Booking) -> dict[str, bool]:
    """Whether each rule had the data it needs. A rule that skips for lack of data is 'not checked',
    never counted as passed."""
    items = bool(b.items)
    return {
        "R-01": items,
        "R-02": items_value(b) is not None and b.total_declared_value is not None,
        "R-03": _all_known(b.items, "quantity", "units_per_carton", "cartons"),
        "R-04": b.cartons is not None and _all_known(b.items, "cartons"),
        "R-05": None not in (b.total_gross_weight_kg, b.pallets, b.destination_country),
        "R-06": items,
        "R-07": goods_weight(b) is not None and b.total_gross_weight_kg is not None,
        "R-08": b.destination_type is not None,
        "R-09": items,
        "R-10": b.ready_date is not None,
    }


def scorecard(b: Booking, issues: list[Issue]) -> list[dict]:
    """One row per rule: {'rule', 'name', 'state'} with state 'pass', 'red', 'amber' or 'unchecked'."""
    broke = {i.rule_id: i.severity for i in issues if i.rule_id in RULE_NAMES}
    can = _checkable(b)
    return [{"rule": r, "name": RULE_NAMES[r],
             "state": broke[r].lower() if r in broke else ("pass" if can[r] else "unchecked")}
            for r in RULE_NAMES]


def run_rules(b: Booking, carriers: list[CarrierOption], today: Optional[date] = None,
              chosen: Optional[CarrierOption] = None) -> list[Issue]:
    """All rulebook issues for one booking, Red first then Amber, in rule order."""
    issues = (r01_hs_code(b) + r02_declared_value(b) + r03_carton_maths(b) + r04_total_cartons(b)
              + r05_pallet_weight(b, carriers, chosen) + r06_dangerous_goods(b) + r07_gross_weight(b)
              + r08_delivery_appointment(b) + r09_country_of_origin(b) + r10_ready_date(b, today))
    return sorted(issues, key=lambda i: (i.severity != "Red", i.rule_id))


def status(issues: list[Issue]) -> str:
    """'Blocked' if any Red, 'Warnings' if any Amber, else 'Ready'."""
    if any(i.severity == "Red" for i in issues):
        return "Blocked"
    if issues:
        return "Warnings"
    return "Ready"


STATUS_BADGE = {"Blocked": "🔴 Blocked", "Warnings": "🟠 Ready with warnings", "Ready": "🟢 Ready to ship"}

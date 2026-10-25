"""Rule-based extractor used when the LLM API is unavailable.

Much less flexible than the LLM, but it understands the common phrasings
("1080 mugs from Manchester to a warehouse in Frankfurt", "£5 each",
"12 per carton", "add a pallet", "yes") so the chat still works.
"""
from __future__ import annotations

import re
from datetime import date, timedelta

from core.chat_agent import ChatState, Extraction, ItemPatch
from core.models import DESTINATIONS, ITEM_ORIGIN_COUNTRIES, ORIGIN_CITIES

NUM = r"(\d+(?:,\d{3})*(?:\.\d+)?)"
WORD_NUMS = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5}
NOT_GOODS = r"(?:pallets?|cartons?|boxes|box|kg|kgs|kilos?|units?\s+per|per|days?|each|x|gbp|pounds?)\b"


def _n(s: str) -> float:
    return float(s.replace(",", ""))


def offline_extract(text: str, state: ChatState, today: date) -> Extraction:
    t = " " + text.strip() + " "
    low = t.lower()
    ex = Extraction()
    b = state.booking
    item = ItemPatch()

    # --- places --------------------------------------------------------------
    dest_cities = [c for cs in DESTINATIONS.values() for c in cs]
    for c in ORIGIN_CITIES:
        if re.search(rf"\b{c.lower()}\b", low):
            ex.origin_city = c
    for c in dest_cities:
        if re.search(rf"\b{c.lower()}\b", low):
            ex.destination_city = c
    if "warehouse" in low or re.search(r"\b(fulfil+ment|distribution) cent(re|er)\b", low):
        ex.destination_type = "Warehouse"
    elif re.search(r"business address|\boffice\b|\bshop\b|\bstore\b|\bbusiness\b", low):
        ex.destination_type = "Business address"

    # --- priority -------------------------------------------------------------
    if re.search(r"cheap|lowest cost|low cost|budget", low):
        ex.seller_priority = "Cheapest"
    elif re.search(r"fast|quick|asap|urgent|soonest", low):
        ex.seller_priority = "Fastest"
    elif re.search(r"reliab|on time|on-time", low):
        ex.seller_priority = "Most reliable"
    elif re.search(r"balanced|no preference|don'?t mind|either", low):
        ex.seller_priority = "Balanced"

    # --- dates ----------------------------------------------------------------
    m = re.search(r"(\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4})", t)
    if m:
        ex.ready_date = m.group(1)
    elif "tomorrow" in low:
        ex.ready_date = (today + timedelta(days=1)).strftime("%d-%m-%Y")
    elif re.search(r"\btoday\b", low):
        ex.ready_date = today.strftime("%d-%m-%Y")
    date_span = m.span() if m else (0, 0)
    scan = t[:date_span[0]] + " " * (date_span[1] - date_span[0]) + t[date_span[1]:]
    scan_low = scan.lower()

    # --- pallets: relative first ---------------------------------------------
    m = re.search(rf"\b(add|plus|another|one more|extra)\s*(a|an|one|two|three|{NUM})?\s*(more\s+)?pallets?", scan_low)
    m2 = re.search(rf"\b(remove|take off|drop|one less|minus)\s*(a|an|one|two|three|{NUM})?\s*pallets?", scan_low)
    if m and b.pallets is not None:
        k = m.group(2)
        ex.pallets = b.pallets + (WORD_NUMS.get(k, None) or (_n(k) if k else 1))
    elif m2 and b.pallets is not None:
        k = m2.group(2)
        ex.pallets = b.pallets - (WORD_NUMS.get(k, None) or (_n(k) if k else 1))
    else:
        m = re.search(rf"{NUM}\s*pallets?", scan_low)
        if m:
            ex.pallets = _n(m.group(1))

    # --- per-carton, cartons ---------------------------------------------------
    m = (re.search(rf"{NUM}\s*(?:units?\s*|pcs\s*|pieces\s*)?(?:per|a|to a|in a|in each|each)\s*(?:carton|box|case)", scan_low)
         or re.search(rf"(?:cartons?|boxes|cases) of {NUM}", scan_low))
    if m:
        item.units_per_carton = _n(m.group(1))
    m = re.search(rf"{NUM}\s*(?:cartons|boxes|cases)\b(?!\s*of)", scan_low)
    if m:
        ex.cartons = _n(m.group(1))
        if len(b.items) <= 1:
            item.cartons = ex.cartons

    # --- money ---------------------------------------------------------------
    for m in re.finditer(rf"(?:£|gbp\s*){NUM}|{NUM}\s*(?:gbp|pounds?)", scan_low):
        val = _n(m.group(1) or m.group(2))
        after = scan_low[m.end():m.end() + 20]
        before_txt = scan_low[max(0, m.start() - 25):m.start()]
        if re.match(r"\s*(each|per|a unit|a piece|apiece|/unit|per unit)", after):
            item.unit_price = val
        elif re.search(r"worth|value|total|declared|in total", before_txt + after):
            ex.total_declared_value = val
        elif b.items and b.items[-1].unit_price is None:
            item.unit_price = val
        else:
            ex.total_declared_value = val

    # --- weights ---------------------------------------------------------------
    for m in re.finditer(rf"{NUM}\s*(?:kg|kgs|kilos?|kilograms?)\b", scan_low):
        val = _n(m.group(1))
        after = scan_low[m.end():m.end() + 20]
        if re.match(r"\s*(each|per|a unit|a piece|apiece|/unit)", after):
            item.unit_weight_kg = val
        else:
            ex.total_gross_weight_kg = val

    # --- HS code, country of origin ------------------------------------------
    m = re.search(r"\bhs(?:\s*code)?\s*(?:is|:|=)?\s*(\d[\d .]{3,}\d)", scan_low)
    if m:
        item.hs_code = m.group(1).replace(" ", "")
        scan_low = scan_low[:m.start()] + " " * (m.end() - m.start()) + scan_low[m.end():]
    m = re.search(r"(?:made|produced|manufactured|origin(?: is)?)\s+in\s+(the\s+)?([a-z ]+?)(?:[,.!]|\s+and\b|$)", low)
    coo = None
    if m:
        coo = next((c for c in ITEM_ORIGIN_COUNTRIES if c.lower() == m.group(2).strip() or
                    (c == "United Kingdom" and m.group(2).strip() in ("uk", "britain", "england"))), m.group(2).strip())
    elif "country_of_origin" in state.last_asked:
        coo = next((c for c in ITEM_ORIGIN_COUNTRIES if c.lower() in low), None)
    if coo:
        item.country_of_origin = coo
    dunno = r"(don'?t know|do not know|no idea|not sure|unsure|unknown)"
    if re.search(rf"{dunno}[^.]{{0,40}}\bhs\b|\bhs\b[^.]{{0,40}}{dunno}", low):
        ex.unknown_fields.append("hs_code")
    if not coo and re.search(rf"{dunno}[^.]{{0,40}}(made|origin)|(made|origin)[^.]{{0,40}}{dunno}", low):
        ex.unknown_fields.append("country_of_origin")

    # --- goods: "1080 mugs", "1,080 ceramic mugs" -------------------------------
    m = re.search(rf"\b{NUM}\s+(?!{NOT_GOODS})([a-z][a-z\- ]{{1,40}}?)(?=\s+(?:from|to|going|for|in|at|that|which)\b|[,.;!]|\s*$)", scan_low)
    if m and not re.match(r"(per|each|to a)\b", m.group(2)):
        item.quantity = _n(m.group(1))
        item.description = m.group(2).strip()
    else:
        m = re.search(rf"{NUM}\s*(?:units|pieces|pcs|items)\b", scan_low)
        if m:
            item.quantity = _n(m.group(1))

    # --- seller name ------------------------------------------------------------
    m = re.search(r"(?i:we'?re|we are|i'?m from|company is|business is|seller is|this is|name is|"
                  r"called|from)\s+([A-Z][\w&'.-]*(?:\s+(?:[A-Z][\w&'.-]*|&|and))*)", t)
    name = re.sub(r"\s+(and|&)$", "", m.group(1).strip()) if m else ""
    if name and name not in ORIGIN_CITIES + dest_cities:
        ex.seller_name = name

    # --- delivery slot / yes-no --------------------------------------------------
    if re.search(r"(slot|appointment)[^.]{0,25}\b(is |has been |already )?booked|booked[^.]{0,15}(slot|appointment)|"
                 r"have a (slot|delivery slot|appointment)", low) and not re.search(r"not booked|n't booked|no slot", low):
        ex.delivery_appointment_booked = True
    elif re.search(r"no (slot|appointment)|(slot|appointment)[^.]{0,20}not booked|haven'?t booked|not yet booked", low):
        ex.delivery_appointment_booked = False
    yes = re.match(r"\s*(yes|yep|yeah|yup|correct|that'?s right|right|ok|okay|sure|confirmed?)\b", low)
    no = re.match(r"\s*(no|nope|not quite|wrong|incorrect)\b", low)
    if state.pending and (yes or no):
        ex.confirms_proposal = bool(yes)
    elif "delivery_appointment_booked" in state.last_asked and ex.delivery_appointment_booked is None and (yes or no):
        ex.delivery_appointment_booked = bool(yes)

    # --- free text answer to a single text question --------------------------
    found_anything = any(v not in (None, [], False) for v in ex.model_dump().values()) or \
        any(v is not None for v in item.model_dump().values())
    if not found_anything and len(text) < 60:
        if "seller_name" in state.last_asked:
            ex.seller_name = text.strip().rstrip(".")
        elif "description" in state.last_asked:
            item.description = text.strip().rstrip(".")

    if any(v is not None for v in item.model_dump().values()):
        ex.items = [item]
    return ex

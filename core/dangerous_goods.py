"""R-06 dangerous goods detection: keywords + HS code prefixes, fully deterministic.

An LLM may later add "possible" flags for borderline items, but only the
signals found here decide a Red.
"""
from __future__ import annotations

import re
from typing import Optional

# keyword -> what it is. Spaces/hyphens in a keyword match space, hyphen or nothing.
KEYWORDS = {
    "lithium": "lithium battery", "li-ion": "lithium battery", "li ion": "lithium battery",
    "lipo": "lithium battery", "power bank": "lithium battery",
    "rechargeable battery": "lithium battery", "battery": "battery (may be lithium)",
    "batteries": "battery (may be lithium)", "e-cigarette": "lithium battery",
    "vape": "lithium battery",
    "aerosol": "aerosol", "spray can": "aerosol", "spray": "aerosol",
    "deodorant spray": "aerosol", "hairspray": "aerosol",
    "perfume": "flammable liquid", "cologne": "flammable liquid",
    "eau de toilette": "flammable liquid", "eau de parfum": "flammable liquid",
    "nail polish": "flammable liquid", "nail varnish": "flammable liquid",
    "lighter": "flammable (lighter)", "lighter fluid": "flammable liquid",
    "butane": "flammable gas", "propane": "flammable gas",
    "fuel": "flammable liquid", "petrol": "flammable liquid", "solvent": "flammable liquid",
    "acetone": "flammable liquid", "paint thinner": "flammable liquid",
    "flammable": "flammable", "hand sanitiser": "flammable liquid (alcohol-based)",
    "hand sanitizer": "flammable liquid (alcohol-based)",
    "alcohol-based": "flammable liquid (alcohol-based)",
    "methylated spirits": "flammable liquid",
    # other names sellers use for the same risks
    "aftershave": "flammable liquid", "body spray": "aerosol", "spray paint": "aerosol",
    "e-liquid": "flammable liquid (vape)", "vape juice": "flammable liquid (vape)",
    "e-cig": "lithium battery", "gas canister": "flammable gas", "camping gas": "flammable gas",
    "matches": "flammable (matches)", "firelighter": "flammable", "nail polish remover": "flammable liquid",
    "white spirit": "flammable liquid", "isopropyl": "flammable liquid", "rubbing alcohol": "flammable liquid",
}

# Phrases that mean the item is NOT dangerous; removed before keyword matching.
NEGATIVE = ["battery-free", "battery free", "no battery", "no batteries", "without battery",
            "without batteries", "batteries not included", "battery not included",
            "non-flammable", "non flammable", "nonflammable", "lighter weight", "lighter than"]

HS_PREFIXES = {
    "8506": "batteries (primary cells)",
    "8507": "batteries (rechargeable, incl. lithium-ion)",
    "3303": "perfumes / toilet waters (flammable)",
    "3605": "matches",
    "3606": "lighter fuel / ferro-cerium",
    "2710": "fuels and oils",
    "3814": "solvents and thinners",
}


def _pattern(kw: str) -> re.Pattern:
    parts = re.split(r"[\s-]+", kw)
    # word-aware: not preceded/followed by a letter, plural 's' allowed
    return re.compile(r"(?<![a-z])" + r"[\s-]?".join(map(re.escape, parts)) + r"s?(?![a-z])")


# Longest first so 'lighter fluid' is reported instead of just 'lighter'.
_KW = sorted(((kw, _pattern(kw), cat) for kw, cat in KEYWORDS.items()), key=lambda t: -len(t[0]))
_NEG = [_pattern(n) for n in sorted(NEGATIVE, key=len, reverse=True)]


def _clean(text: str) -> str:
    t = text.lower()
    for p in _NEG:
        t = p.sub(" ", t)
    return t


def detect(description: Optional[str], sku: Optional[str], hs_code: Optional[str]) -> list[str]:
    """Return human-readable signals, e.g. "Description contains 'power bank' (lithium battery)"."""
    signals: list[str] = []
    for field, value in (("Description", description), ("SKU", sku)):
        if not value:
            continue
        t = _clean(value)
        for kw, pat, cat in _KW:
            m = pat.search(t)
            if m:
                signals.append(f"{field} contains '{kw}' ({cat})")
                t = t[:m.start()] + " " + t[m.end():]   # don't double-report 'lighter' in 'lighter fluid'
    word = possible_battery(description)
    said_none = any(p.search((description or "").lower()) for p in _NEG)    # e.g. "no battery"
    if word and not said_none and not any("batter" in s for s in signals):
        signals.append(f"Description says '{word}': this kind of product usually has a built-in lithium battery")
    digits = re.sub(r"\D", "", hs_code or "")
    for prefix, what in HS_PREFIXES.items():
        if digits.startswith(prefix):
            signals.append(f"HS code {hs_code} starts with {prefix} ({what})")
    return signals


# Products that usually contain a built-in lithium battery even when the description doesn't say
# "lithium" (e.g. wireless earbuds with a charging case). R-06 flags them Red; the seller can clear it
# by confirming there is no battery and saying so in the description ("no battery").
BATTERY_DEVICES = [
    "earbuds", "earphones", "headphones", "headset", "airpods", "bluetooth", "wireless speaker",
    "smartwatch", "smart watch", "fitness tracker", "smartphone", "mobile phone", "laptop", "tablet",
    "e-reader", "electric toothbrush", "electric shaver", "hair clipper", "drone", "e-scooter",
    "electric scooter", "hoverboard", "rechargeable", "cordless", "usb-c powered", "camera",
]
_DEVICE = [(w, _pattern(w)) for w in sorted(BATTERY_DEVICES, key=len, reverse=True)]


def possible_battery(description: Optional[str]) -> Optional[str]:
    """The device word found, if the product probably has a built-in battery (else None)."""
    t = _clean(description or "")
    for word, pat in _DEVICE:
        if pat.search(t):
            return word
    return None

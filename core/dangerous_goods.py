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
    digits = re.sub(r"\D", "", hs_code or "")
    for prefix, what in HS_PREFIXES.items():
        if digits.startswith(prefix):
            signals.append(f"HS code {hs_code} starts with {prefix} ({what})")
    return signals

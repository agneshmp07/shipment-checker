"""Certain corrections for misspelled choices: 'Germny' -> 'Germany', 'UK' -> 'United Kingdom', 'Yse' -> Yes.

A correction is offered only when it is unambiguous: a known alias, or one allowed value that is clearly
closer than every other (similarity >= 0.75 and at least 0.15 ahead of the next). Anything less certain is
left for the person to choose.
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Optional

ALIASES = {
    "uk": "United Kingdom", "gb": "United Kingdom", "great britain": "United Kingdom", "britain": "United Kingdom",
    "england": "United Kingdom", "scotland": "United Kingdom", "wales": "United Kingdom",
    "northern ireland": "United Kingdom", "united kingdom of great britain": "United Kingdom",
    "holland": "Netherlands", "the netherlands": "Netherlands", "nl": "Netherlands", "nederland": "Netherlands",
    "deutschland": "Germany", "de": "Germany", "fr": "France",
    "prc": "China", "peoples republic of china": "China", "viet nam": "Vietnam", "turkiye": "Turkey",
    "türkiye": "Turkey", "frankfurt am main": "Frankfurt",
    "business": "Business address", "office": "Business address", "wh": "Warehouse",
    "cheap": "Cheapest", "fast": "Fastest", "reliable": "Most reliable",
}
YES = {"yse", "yes.", "yess", "ye", "yeah", "yep", "booked", "confirmed"}
NO = {"noo", "nope", "nah", "not booked", "none", "not yet", "pending"}


def _key(v) -> str:
    return re.sub(r"[^a-zà-ÿ0-9 ]", "", re.sub(r"\s+", " ", str(v).strip().lower())).strip()


def correct(raw, allowed: list[str]) -> Optional[str]:
    """The one allowed value this clearly meant, or None if it isn't certain."""
    key = _key(raw)
    if not key:
        return None
    if ALIASES.get(key) in allowed:
        return ALIASES[key]
    if len(key) < 3:
        return None
    scores = sorted(((SequenceMatcher(None, key, _key(a)).ratio(), a) for a in allowed), reverse=True)
    best, second = scores[0][0], (scores[1][0] if len(scores) > 1 else 0.0)
    return scores[0][1] if best >= 0.75 and best - second >= 0.15 else None


def yes_no(raw) -> Optional[bool]:
    """True/False when a Yes/No answer is clearly meant ('Yse', 'booked', 'not yet'), else None."""
    key = _key(raw)
    if key in YES:
        return True
    if key in NO:
        return False
    guess = correct(raw, ["Yes", "No"]) if len(key) >= 3 else None
    return None if guess is None else guess == "Yes"

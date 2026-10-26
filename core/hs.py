"""Is this a real HS code? A structural check against the Harmonized System (HS 2022).

Six digits isn't enough: '123456' has six digits but chapter 12 only has headings 1201-1214, so it can't
be a real code. We check the chapter exists (01-97; 77 is reserved) and the heading (first 4 digits) is
within that chapter's range. A code that fails is never accepted, by the rules or in the Fix window.
"""
from __future__ import annotations

import re
from typing import Optional

# chapter -> last heading in that chapter (HS 2022), e.g. chapter 12 runs 1201-1214
LAST_HEADING = {
    1: 6, 2: 10, 3: 9, 4: 10, 5: 11, 6: 4, 7: 14, 8: 14, 9: 10, 10: 8, 11: 9, 12: 14, 13: 2, 14: 4, 15: 22,
    16: 5, 17: 4, 18: 6, 19: 5, 20: 9, 21: 6, 22: 9, 23: 9, 24: 4, 25: 30, 26: 21, 27: 16, 28: 53, 29: 42,
    30: 6, 31: 5, 32: 15, 33: 7, 34: 7, 35: 7, 36: 6, 37: 7, 38: 27, 39: 26, 40: 17, 41: 15, 42: 6, 43: 4,
    44: 21, 45: 4, 46: 2, 47: 7, 48: 23, 49: 11, 50: 7, 51: 13, 52: 12, 53: 11, 54: 8, 55: 16, 56: 9, 57: 5,
    58: 11, 59: 11, 60: 6, 61: 17, 62: 17, 63: 10, 64: 6, 65: 7, 66: 3, 67: 4, 68: 15, 69: 14, 70: 20,
    71: 18, 72: 29, 73: 26, 74: 19, 75: 8, 76: 16, 78: 6, 79: 7, 80: 7, 81: 13, 82: 15, 83: 11, 84: 87,
    85: 49, 86: 9, 87: 16, 88: 7, 89: 8, 90: 33, 91: 14, 92: 9, 93: 7, 94: 6, 95: 8, 96: 20, 97: 6,
}


def problem(code: Optional[str]) -> Optional[str]:
    """Why this isn't a usable HS code, or None if it is (6-10 digits, real chapter and heading)."""
    raw = (code or "").strip()
    if not raw:
        return "it's missing"
    if re.search(r"[^\d\s.]", raw):
        return f"'{raw}' has letters or symbols — an HS code is digits only"
    d = re.sub(r"\D", "", raw)
    if len(d) < 6:
        return f"'{raw}' has only {len(d)} digits; at least 6 are needed"
    if len(d) > 10:
        return f"'{raw}' has {len(d)} digits; HS codes have at most 10"
    chapter, heading = int(d[:2]), int(d[2:4])
    if chapter not in LAST_HEADING:
        return f"'{raw}' isn't a real HS code — chapter {d[:2]} doesn't exist (chapters run 01–97)"
    last = LAST_HEADING[chapter]
    if not 1 <= heading <= last:
        return (f"'{raw}' isn't a real HS code — heading {d[:4]} doesn't exist "
                f"(chapter {d[:2]} only has headings {d[:2]}01–{d[:2]}{last:02d})")
    return None

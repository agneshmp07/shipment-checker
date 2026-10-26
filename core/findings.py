"""Plain-English findings for one booking: what's wrong, what to fix, what we recommend.

Used by the "What we found in your file" pop-up. Built only from the rule results and the
diagnosis, so it always agrees with the detailed view.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from core.check import Evaluation
from core.diagnosis import diagnose

CONFIDENCE_WORDS = {"High": "we're confident about this",
                    "Medium": "this is the most likely cause",
                    "Low": "a possible cause — please check"}


# How to name several issues of one rule together: "the 2 HS codes"
PLURALS = {"R-01": "HS codes", "R-03": "items' carton counts", "R-06": "dangerous items",
           "R-09": "countries of origin"}


def _what(issues: list) -> str:
    n, first = len(issues), issues[0]
    if n == 1:
        return f"“{first.title}”"
    if first.rule_id in PLURALS:
        return f"the {n} {PLURALS[first.rule_id]}"
    return f"“{first.title}” ({n} items)"


class Findings(BaseModel):
    wrong: list[str] = Field(default_factory=list)       # each problem, with its numbers
    fix: list[str] = Field(default_factory=list)         # the exact change to make
    recommend: list[str] = Field(default_factory=list)   # our best guess, with how sure we are


def findings(ev: Evaluation) -> Findings:
    out = Findings()
    for i in ev.issues:                                  # already ordered: must-fix first
        label = "Must fix" if i.severity == "Red" else "Warning"
        out.wrong.append(f"{label} — {i.title}: {i.explanation}")
    roots, rest = diagnose(ev.booking, ev.issues)
    for r in roots:
        out.fix.append(f"{r.fix_label}." if r.fix_action else r.title + ".")
        out.recommend.append(f"{r.title} ({CONFIDENCE_WORDS[r.confidence]}). {r.explanation}")
    for i in rest:
        out.fix.append(i.fix)
    if not out.recommend and rest:
        first = rest[0]
        if len(ev.issues) == 1:
            out.recommend.append("Once you've done this, the booking is ready to ship."
                                 if first.severity == "Red" else
                                 "It can ship as it is, but fixing this avoids delays at delivery.")
        else:
            groups: dict[str, list] = {}                 # one entry per rule, in order of importance
            for i in rest:
                groups.setdefault(i.rule_id, []).append(i)
            parts = list(groups.values())
            reason = "it stops the shipment" if first.severity == "Red" else "it's the most likely to cause a delay"
            if len(parts) == 1:
                done = "ready to ship" if first.severity == "Red" else "clear of warnings"
                out.recommend.append(f"Fix {_what(parts[0])} — {reason}. Then the booking is {done}.")
            else:
                others = "; ".join(_what(p) for p in parts[1:])
                out.recommend.append(f"Start with {_what(parts[0])} — {reason}. Then: {others}.")
    return out

"""One call that every screen uses: Booking -> issues, carrier, status, confirmation.

Chat and file upload both go through evaluate(), so they always agree.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from core import confirmation, rules
from core.carriers import recommend
from core.models import Booking, CarrierOption, Issue, Recommendation


@dataclass
class Evaluation:
    booking: Booking
    issues: list[Issue]                 # data issues + rulebook issues, Red first
    recommendation: Recommendation
    status: str                         # "Blocked" / "Warnings" / "Ready"
    summary: str
    next_steps: list[dict] = field(default_factory=list)

    @property
    def badge(self) -> str:
        return rules.STATUS_BADGE[self.status]


def evaluate(b: Booking, carriers: list[CarrierOption], today: Optional[date] = None) -> Evaluation:
    rec = recommend(b, carriers)
    # R-05 checks against the recommended carrier ("the chosen carrier").
    chosen = rec.winner.option if rec.winner else None
    issues = rules.run_rules(b, carriers, today, chosen) + b.data_issues
    issues.sort(key=lambda i: (i.severity != "Red", i.rule_id == "DATA", i.rule_id))
    dg = sorted({i.item_sku or "an item" for i in issues if i.rule_id == "R-06"})
    if dg:      # dangerous goods: no carrier on this service takes them, so none is recommended
        rec = rec.model_copy(update={
            "winner": None, "runner_up": None, "trade_off": "", "headline": "", "ruled_out": "",
            "reason": f"No carrier: this road service can't carry dangerous goods (R-06: {', '.join(dg)}). "
                      "Remove the item, or confirm it isn't dangerous and say so in the description; "
                      "then a carrier is picked.",
            "all_options": [r.model_copy(update={"status": "Eliminated", "reason": "Dangerous goods (R-06)"})
                            for r in rec.all_options]})
    return Evaluation(booking=b, issues=issues, recommendation=rec, status=rules.status(issues),
                      summary=confirmation.summary(b, rec, issues),
                      next_steps=confirmation.next_steps(b, rec, issues))

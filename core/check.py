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
    return Evaluation(booking=b, issues=issues, recommendation=rec, status=rules.status(issues),
                      summary=confirmation.summary(b, rec, issues),
                      next_steps=confirmation.next_steps(b, rec, issues))

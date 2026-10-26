"""Phase 3 acceptance: every planted mistake is caught, clean bookings get no Reds."""
from datetime import date

import pytest

from core import rules
from core.excel_loader import load_workbook
from tests.fixtures.make_planted_mistakes import CLEAN, EXPECTED, OUT, build

TODAY = date(2026, 10, 25)


@pytest.fixture(scope="module")
def loaded():
    build()                       # regenerate so the file always matches the answer key
    return load_workbook(OUT)


def found_rules(b, carriers):
    issues = rules.run_rules(b, carriers, TODAY) + b.data_issues
    return issues, {i.rule_id for i in issues}


def test_all_bookings_loaded(loaded):
    assert {b.booking_id for b in loaded.bookings} == set(EXPECTED)


@pytest.mark.parametrize("booking_id", sorted(EXPECTED))
def test_exact_rules_caught(loaded, carriers, booking_id):
    b = next(b for b in loaded.bookings if b.booking_id == booking_id)
    _, found = found_rules(b, carriers)
    assert found == EXPECTED[booking_id], f"{booking_id}: expected {EXPECTED[booking_id]}, got {found}"


def test_clean_bookings_have_no_reds(loaded, carriers):
    for b in loaded.bookings:
        if b.booking_id in CLEAN:
            issues, _ = found_rules(b, carriers)
            assert rules.status(issues) == "Ready", (b.booking_id, [i.title for i in issues])


def test_every_rule_planted_at_least_once():
    planted = set().union(*EXPECTED.values())
    assert {f"R-{n:02d}" for n in range(1, 11)} <= planted


def test_orphan_item_reported(loaded):
    assert any("BK-999" in i.explanation for i in loaded.file_issues)


def test_lost_leading_zero_hint(loaded, carriers):
    b = next(b for b in loaded.bookings if b.booking_id == "BK-105")
    (issue,) = [i for i in rules.run_rules(b, carriers, TODAY) if i.rule_id == "R-01"]
    assert "090111" in issue.explanation and issue.fix_action["value"] == "090111" and issue.fix_action["certain"]

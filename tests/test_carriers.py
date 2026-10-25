"""Carrier ranking, elimination and confirmation (Phase 4)."""
from datetime import date

import pytest

from core import confirmation
from core.carriers import recommend
from core.check import evaluate
from tests.conftest import _c
from tests.test_rules import booking

TODAY = date(2026, 10, 25)

# TEST-ONLY rate card with hand-checkable numbers (all UK -> Germany).
A = _c("Test A", "Germany", 180, 5, 92, 500)
B = _c("Test B", "Germany", 250, 3, 96, 400)
C = _c("Test C", "Germany", 150, 7, 85, 600)
D = _c("Test D", "Germany", 180, 5, 95, 300)
FR = _c("Test FR", "France", 100, 2, 99, 900)     # other route: must never be picked for Germany
CARDS = [A, B, C, D, FR]


def winner(priority, **kw):
    rec = recommend(booking(seller_priority=priority, **kw), CARDS)
    return rec, rec.winner.option.carrier, rec.runner_up.option.carrier if rec.runner_up else None


def test_cheapest_with_on_time_tie_break():
    rec, win, run = winner("Cheapest")            # 3 pallets
    assert (win, run) == ("Test C", "Test D")     # A and D both £540; D has higher on-time
    assert rec.winner.total_cost == 450
    assert "3 pallets × £150.00 = £450.00" in rec.reason


def test_fastest():
    rec, win, _ = winner("Fastest")
    assert win == "Test B" and "3 days" in rec.reason


def test_most_reliable():
    rec, win, run = winner("Most reliable")
    assert (win, run) == ("Test B", "Test D") and "96%" in rec.reason


def test_balanced_scores_and_weights_stated():
    # cost (lower better):  A .70  B 0    C 1    D .70
    # speed (lower better): A .50  B 1    C 0    D .50
    # on-time:              A .636 B 1    C 0    D .909
    # score = .4c + .3s + .3r -> A .621  B .600  C .400  D .703
    rec, win, run = winner("Balanced")
    assert (win, run) == ("Test D", "Test A")
    assert rec.winner.score == pytest.approx(0.703, abs=0.001)
    assert "cost (40%), speed (30%) and reliability (30%)" in rec.reason


def test_missing_priority_defaults_to_balanced():
    rec = recommend(booking(seller_priority=None), CARDS)
    assert rec.winner.option.carrier == "Test D" and rec.reason.startswith("No priority given")


def test_only_route_carriers_listed():
    rec = recommend(booking(), CARDS)
    assert {r.option.carrier for r in rec.all_options} == {"Test A", "Test B", "Test C", "Test D"}


def test_elimination_by_weight_with_reason():
    rec = recommend(booking(total_gross_weight_kg=1350), CARDS)       # 450 kg per pallet
    status = {r.option.carrier: r.status for r in rec.all_options}
    assert status == {"Test C": "Recommended", "Test A": "Runner-up",
                      "Test B": "Eliminated", "Test D": "Eliminated"}
    elim_b = next(r for r in rec.all_options if r.option.carrier == "Test B")
    assert "Max 400 kg per pallet" in elim_b.reason and "450 kg" in elim_b.reason


def test_no_eligible_carrier():
    rec = recommend(booking(total_gross_weight_kg=2000, pallets=1), CARDS)
    assert rec.winner is None and "at least 4 pallets" in rec.reason       # ceil(2000/600)
    assert all(r.status == "Eliminated" for r in rec.all_options)
    ev = evaluate(booking(total_gross_weight_kg=2000, pallets=1), CARDS, TODAY)
    r05 = [i for i in ev.issues if i.rule_id == "R-05"]
    assert r05 and r05[0].fix_action["value"] == 4 and ev.status == "Blocked"


def test_no_route():
    rec = recommend(booking(destination_country="Netherlands", destination_city="Amsterdam"), CARDS)
    assert rec.winner is None and "No carrier" in rec.reason


def test_missing_pallets_no_crash():
    rec = recommend(booking(pallets=None), CARDS)
    assert rec.winner is None and "pallets" in rec.reason


def test_trade_off_text():
    rec, *_ = winner("Cheapest")
    assert rec.trade_off == ("£90.00 cheaper but 2 days slower and 10 points less reliable on time "
                             "than the runner-up, Test D (Test service).")


def test_confirmation_and_delivery_date():
    ev = evaluate(booking(ready_date=date(2026, 11, 5)), CARDS, TODAY)   # Cheapest -> C, 7 days
    assert ev.status == "Ready"
    assert confirmation.delivery_date(ev.booking, ev.recommendation) == date(2026, 11, 12)
    assert ev.summary == ("Your 90 cartons (1,080 units) on 3 pallets will be collected from Manchester "
                          "on 05-11-2026 by Test C (Test service) and should arrive in Frankfurt around "
                          "12-11-2026. Cost: £450.00.")
    steps = [s["step"] for s in ev.next_steps]
    assert steps == ["Book the delivery slot", "Label cartons", "Prepare the commercial invoice",
                     "Collection", "Delivery"]


def test_confirmation_when_blocked():
    ev = evaluate(booking(cartons=95, delivery_appointment_booked=False), CARDS, TODAY)
    assert ev.summary.startswith("Once the 1 red issue is fixed: your 95 cartons")   # as stated
    assert ev.next_steps[0]["step"] == "Fix red issues"
    slot = next(s for s in ev.next_steps if s["step"] == "Book the delivery slot")
    assert slot["state"] == "todo"

"""Phase 7: which number is wrong, root-cause grouping, apply fix."""
from datetime import date

from core import rules
from core.check import evaluate
from core.diagnosis import apply_fix, diagnose, looks_like_typo
from core.excel_loader import load_workbook
from tests.conftest import STANDIN_CARRIERS
from tests.fixtures.make_planted_mistakes import OUT, build
from tests.test_rules import booking, item

TODAY = date(2026, 10, 25)


def run(b):
    issues = rules.run_rules(b, STANDIN_CARRIERS, TODAY)
    return issues, *diagnose(b, issues)


def test_wrong_item_cartons_groups_r03_and_r04():
    b = booking([item(cartons=80)], cartons=90)          # BK-107 pattern
    issues, roots, remaining = run(b)
    assert {i.rule_id for i in issues} == {"R-03", "R-04"}
    (rc,) = roots
    assert rc.title == "Most likely typo: cartons for MUG-01 should be 90, not 80"
    assert rc.confidence == "High" and rc.fixes == ["R-03:MUG-01", "R-04:"]
    assert "declared value £5,400.00 matches quantity 1,080" in rc.explanation
    assert remaining == []
    apply_fix(b, rc.fix_action)
    assert rules.run_rules(b, STANDIN_CARRIERS, TODAY) == []


def test_wrong_quantity_groups_r03_and_r02():
    b = booking([item(quantity=1000)])                   # 12 × 90 = 1,080 and £5,400 = 1,080 × £5
    issues, roots, remaining = run(b)
    assert {i.rule_id for i in issues} == {"R-02", "R-03"}
    (rc,) = roots
    assert rc.title == "Most likely typo: quantity for MUG-01 should be 1,080, not 1,000"
    assert rc.confidence == "High" and set(rc.fixes) == {"R-02:", "R-03:MUG-01"}
    apply_fix(b, rc.fix_action)
    assert rules.run_rules(b, STANDIN_CARRIERS, TODAY) == []


def test_wrong_units_per_carton_when_everything_else_agrees():
    b = booking([item(units_per_carton=10)])             # 10 × 90 = 900 ≠ 1,080; value + cartons agree
    _, roots, _ = run(b)
    assert roots[0].title == "Most likely typo: units per carton for MUG-01 should be 12, not 10"


def test_declared_value_swapped_digits():
    b = booking(total_declared_value=4500)               # items = £5,400
    _, roots, remaining = run(b)
    (rc,) = roots
    assert "declared value is wrong: it should be £5,400.00" in rc.title
    assert rc.confidence == "High" and "two swapped digits" in rc.explanation
    assert remaining == []


def test_price_typo_mentions_alternative():
    b = booking([item(), item(sku="BOWL-02", description="Bowl", quantity=240, unit_price=5.5,
                              units_per_carton=24, cartons=10)],
                cartons=100, total_declared_value=6840, total_gross_weight_kg=760)   # true bowl price £6.00
    _, roots, _ = run(b)
    (rc,) = roots
    text = rc.title + rc.explanation
    assert "£6.00" in text and "BOWL-02" in text


def test_booking_total_cartons_wrong():
    b = booking(cartons=95)
    _, roots, _ = run(b)
    (rc,) = roots
    assert rc.title.startswith("Most likely the booking's carton total is wrong: it should be 90")
    assert rc.confidence == "High"


def test_unrelated_issues_stay_separate():
    b = booking([item(cartons=80, country_of_origin=None)], cartons=90, delivery_appointment_booked=False)
    issues, roots, remaining = run(b)
    assert len(roots) == 1 and {i.rule_id for i in remaining} == {"R-08", "R-09"}


def test_typo_patterns():
    assert looks_like_typo(5400, 4500) == "two swapped digits"
    assert looks_like_typo(540, 5400) == "an extra or missing zero"
    assert looks_like_typo(80, 90) == "one mistyped digit"
    assert looks_like_typo(80, 135) is None


def test_apply_fix_report_and_date():
    b = booking(ready_date=date(2026, 10, 1))
    assert apply_fix(b, {"target": "booking", "field": "ready_date", "value": "2026-10-25"}) == \
        "ready date: 01-10-2026 → 25-10-2026"
    assert apply_fix(b, {"target": "item", "sku": "MUG-01", "field": "cartons", "value": 91.0}) == \
        "cartons for MUG-01: 90 → 91"


def test_fixture_bk107_and_bk112():
    build()
    res = load_workbook(OUT)
    get = {b.booking_id: b for b in res.bookings}
    ev = evaluate(get["BK-107"], STANDIN_CARRIERS, TODAY)
    roots, remaining = diagnose(ev.booking, ev.issues)
    assert roots[0].title == "Most likely typo: cartons for MUG-01 should be 90, not 80"
    assert len(roots[0].fixes) == 2 and remaining == []
    apply_fix(ev.booking, roots[0].fix_action)
    assert evaluate(ev.booking, STANDIN_CARRIERS, TODAY).status == "Ready"

    # BK-112: SOAP-02 has 20 per carton × 18 cartons = 360 but quantity 400 -> cartons should be 20
    ev = evaluate(get["BK-112"], STANDIN_CARRIERS, TODAY)
    roots, _ = diagnose(ev.booking, ev.issues)
    soap = next(r for r in roots if "SOAP-02" in r.title)
    assert "cartons for SOAP-02 should be 20" in soap.title or "quantity for SOAP-02" in soap.title


def test_r07_gross_weight_estimate_with_fix():
    b = booking(total_gross_weight_kg=400)               # goods 1,080 × 0.5 = 540 kg, 3 pallets
    issues, roots, remaining = run(b)
    (rc,) = roots
    assert rc.title == ("Most likely the gross weight is too low: raise it to at least 615 kg plus packaging, "
                        "not 400 kg")
    assert "540 kg goods + 3 × 25 kg empty pallets" in rc.explanation and "re-weigh" in rc.fix_label
    assert remaining == []
    apply_fix(b, rc.fix_action)
    assert rules.run_rules(b, STANDIN_CARRIERS, TODAY) == []


def test_r07_never_shrinks_a_products_weight():
    b = booking([item(unit_weight_kg=5.0)])              # 1,080 × 5 kg = 5,400 kg > 620 kg gross
    _, roots, _ = run(b)
    (rc,) = roots
    assert rc.fix_action["field"] == "total_gross_weight_kg" and rc.fix_action["value"] >= 5400
    assert "raise it to at least" in rc.title and "plus packaging" in rc.title

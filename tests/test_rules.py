"""At least one passing and one failing test per rule, plus edge cases."""
from datetime import date, timedelta

import pytest

from core import rules
from core.dangerous_goods import detect
from core.models import Booking, CarrierOption, Item

TODAY = date(2026, 10, 25)

# TEST-ONLY carriers (not the real rate card, which lives in data/carriers.json).
TEST_CARRIERS = [
    CarrierOption(carrier="Test A", service="Road", origin_country="United Kingdom",
                  destination_country="Germany", price_per_pallet=180, transit_days=5,
                  on_time_rate=92, max_weight_per_pallet_kg=500),
    CarrierOption(carrier="Test B", service="Express", origin_country="United Kingdom",
                  destination_country="Germany", price_per_pallet=250, transit_days=3,
                  on_time_rate=96, max_weight_per_pallet_kg=300),
]


def item(**kw) -> Item:
    base = dict(booking_id="BK-001", sku="MUG-01", description="Ceramic coffee mug, 350 ml",
                hs_code="691200", quantity=1080, unit_price=5.0, units_per_carton=12, cartons=90,
                unit_weight_kg=0.5, country_of_origin="United Kingdom")
    base.update(kw)
    return Item(**base)


def booking(items=None, **kw) -> Booking:
    base = dict(booking_id="BK-001", seller_name="Northfield Goods", origin_city="Manchester",
                destination_city="Frankfurt", destination_country="Germany",
                destination_type="Warehouse", ready_date=date(2026, 11, 5), seller_priority="Cheapest",
                pallets=3, cartons=90, total_declared_value=5400, total_gross_weight_kg=620,
                delivery_appointment_booked=True)
    base.update(kw)
    return Booking(items=items if items is not None else [item()], **base)


def ids(issues):
    return [i.rule_id for i in issues]


def test_clean_booking_passes_everything():
    issues = rules.run_rules(booking(), TEST_CARRIERS, TODAY)
    assert issues == []
    assert rules.status(issues) == "Ready"


# R-01 ------------------------------------------------------------------------
def test_r01_pass_with_dots_and_spaces():
    assert rules.r01_hs_code(booking([item(hs_code="6912.00 10")])) == []


def test_r01_blank_fails():
    (i,) = rules.r01_hs_code(booking([item(hs_code=None)]))
    assert i.severity == "Red" and "no HS code" in i.explanation


def test_r01_short_fails_with_digit_count():
    (i,) = rules.r01_hs_code(booking([item(hs_code="6912")]))
    assert "only 4 digits" in i.explanation


def test_r01_five_digits_lost_zero_hint_when_the_chapter_fits():
    (i,) = rules.r01_hs_code(booking([item(description="Roasted coffee beans, 1 kg bag", hs_code="90121",
                                           hs_possible_leading_zero_lost=True)]))
    assert i.severity == "Red" and "dropped the leading zero" in i.explanation and "coffee, tea and spices" in i.explanation
    assert i.fix_action["value"] == "090121" and i.fix_action["certain"]     # sure: real code, chapter fits


@pytest.mark.parametrize("code", ["123456", "999999", "000000", "770000", "620000", "12345678901", "12a456"])
def test_r01_rejects_codes_that_are_not_real(code):
    (i,) = rules.r01_hs_code(booking([item(hs_code=code)]))
    assert i.severity == "Red" and i.fix_action is None


@pytest.mark.parametrize("code", ["691200", "090121", "8544.42", "6109100010", "940360"])
def test_r01_accepts_real_codes(code):
    assert rules.r01_hs_code(booking([item(hs_code=code)])) == []


def test_r01_no_zero_hint_when_the_chapter_does_not_fit():
    (i,) = rules.r01_hs_code(booking([item(description="USB-C charging cable, 1 m", hs_code="85444",
                                           hs_possible_leading_zero_lost=True)]))
    assert i.severity == "Red" and "085444" not in i.fix and i.fix_action is None
    assert "too short" not in i.fix and "at least 6 digits" in i.fix


# R-02 ------------------------------------------------------------------------
def test_r02_exact_passes():
    assert rules.r02_declared_value(booking()) == []


def test_r02_exactly_one_percent_passes():
    assert rules.r02_declared_value(booking(total_declared_value=5454)) == []   # 5400 * 1.01


def test_r02_just_over_one_percent_fails():
    (i,) = rules.r02_declared_value(booking(total_declared_value=5454.01))
    assert i.severity == "Red"


def test_r02_message_has_numbers():
    (i,) = rules.r02_declared_value(booking(total_declared_value=5400,
                                            items=[item(quantity=1188, cartons=99)]))
    assert "£5,400.00" in i.explanation and "£5,940.00" in i.explanation
    assert "£540.00" in i.explanation and "9.1%" in i.explanation


# R-03 ------------------------------------------------------------------------
def test_r03_pass():
    assert rules.r03_carton_maths(booking()) == []


def test_r03_fail_suggests_cartons():
    (i,) = rules.r03_carton_maths(booking([item(cartons=80)], cartons=80))
    assert "960" in i.explanation and "1,080" in i.explanation
    assert i.fix_action == {"target": "item", "sku": "MUG-01", "field": "cartons", "value": 90}


# R-04 ------------------------------------------------------------------------
def test_r04_pass_multi_item():
    b = booking([item(), item(sku="BOWL-02", quantity=240, units_per_carton=24, cartons=10)], cartons=100)
    assert rules.r04_total_cartons(b) == []


def test_r04_fail():
    (i,) = rules.r04_total_cartons(booking(cartons=95))
    assert "95" in i.explanation and "90" in i.explanation and i.fix_action["value"] == 90


# R-05 ------------------------------------------------------------------------
def test_r05_pass():
    assert rules.r05_pallet_weight(booking(), TEST_CARRIERS) == []   # 207 kg/pallet


def test_r05_chosen_carrier_too_small():
    (i,) = rules.r05_pallet_weight(booking(), TEST_CARRIERS, chosen=TEST_CARRIERS[1].model_copy(
        update={"max_weight_per_pallet_kg": 200}))
    assert "206.7 kg" in i.explanation


def test_r05_no_carrier_can_take_it_gives_min_pallets():
    (i,) = rules.r05_pallet_weight(booking(total_gross_weight_kg=1600, pallets=2), TEST_CARRIERS)
    assert "800 kg" in i.explanation and "at least 4 pallets" in i.fix   # ceil(1600/500)
    assert i.fix_action["value"] == 4


def test_r05_zero_pallets_no_crash():
    (i,) = rules.r05_pallet_weight(booking(pallets=0), TEST_CARRIERS)
    assert i.severity == "Red" and "Pallets is 0" in i.explanation


def test_r05_no_route():
    (i,) = rules.r05_pallet_weight(booking(destination_country="France", destination_city="Paris"),
                                   TEST_CARRIERS)
    assert "No carrier" in i.title


# R-06 ------------------------------------------------------------------------
@pytest.mark.parametrize("desc", ["Portable power bank 10000mAh", "Li-ion battery pack",
                                  "Hairspray 250ml", "Eau de toilette 100 ml", "Nail polish set",
                                  "Lighter fluid refill", "Alcohol-based hand sanitiser"])
def test_r06_flags(desc):
    (i,) = rules.r06_dangerous_goods(booking([item(description=desc, hs_code="999999")]))
    assert i.severity == "Red" and "contains" in i.explanation


@pytest.mark.parametrize("desc", ["Ceramic coffee mug, 350 ml", "Battery-free LED candle",
                                  "Torch (batteries not included)", "Non-flammable cleaning cloth",
                                  "Lighter weight cotton t-shirt", "Spoon"])
def test_r06_no_false_positive(desc):
    assert rules.r06_dangerous_goods(booking([item(description=desc)])) == []


def test_r06_hs_prefix_and_signal_text():
    assert detect("Gift item", "GIFT-1", "850760") == [
        "HS code 850760 starts with 8507 (batteries (rechargeable, incl. lithium-ion))"]
    assert detect("Power bank", None, None) == ["Description contains 'power bank' (lithium battery)"]


# R-07 ------------------------------------------------------------------------
def test_r07_pass_equal_is_ok():
    assert rules.r07_gross_weight(booking(total_gross_weight_kg=540)) == []


def test_r07_fail():
    (i,) = rules.r07_gross_weight(booking(total_gross_weight_kg=400))
    assert i.severity == "Amber" and "400 kg" in i.explanation and "540 kg" in i.explanation
    assert i.title == "Gross weight lighter than the goods"


def test_heavy_but_plausible_has_no_note():
    # 540 kg goods on 3 pallets: at most 540 × 1.6 + 3 × 30 + 25 = 979 kg
    assert rules.weight_note(booking(total_gross_weight_kg=979)) is None


def test_far_too_heavy_is_a_note_not_a_rule_break():
    b = booking(total_gross_weight_kg=6200)                  # an extra digit on 620
    assert rules.r07_gross_weight(b) == []                   # R-07 only asks for "at least the goods"
    note = rules.weight_note(b)
    assert "6,200 kg" in note and "979 kg" in note and "doesn't change the status" in note


# R-08 ------------------------------------------------------------------------
def test_r08_pass_business_address_without_slot():
    assert rules.r08_delivery_appointment(booking(destination_type="Business address",
                                                  delivery_appointment_booked=False)) == []


def test_r08_fail():
    (i,) = rules.r08_delivery_appointment(booking(delivery_appointment_booked=False))
    assert i.severity == "Amber" and "Frankfurt" in i.explanation


# R-09 ------------------------------------------------------------------------
def test_r09_pass():
    assert rules.r09_country_of_origin(booking()) == []


def test_r09_fail():
    (i,) = rules.r09_country_of_origin(booking([item(country_of_origin=None)]))
    assert i.severity == "Amber" and i.item_sku == "MUG-01"


# R-10 ------------------------------------------------------------------------
def test_r10_today_is_allowed():
    assert rules.r10_ready_date(booking(ready_date=TODAY), TODAY) == []


def test_r10_yesterday_fails():
    (i,) = rules.r10_ready_date(booking(ready_date=TODAY - timedelta(days=1)), TODAY)
    assert i.severity == "Amber" and "1 day before" in i.explanation


# Robustness ------------------------------------------------------------------
def test_missing_values_never_crash():
    b = Booking(items=[Item()])
    issues = rules.run_rules(b, TEST_CARRIERS, TODAY)
    assert set(ids(issues)) == {"R-01", "R-09"}   # everything else lacks inputs (DATA issues cover it)


def test_status_ordering_and_multi_error():
    b = booking([item(cartons=80, hs_code=None, country_of_origin=None)],
                delivery_appointment_booked=False, ready_date=date(2026, 10, 1))
    issues = rules.run_rules(b, TEST_CARRIERS, TODAY)
    assert ids(issues) == ["R-01", "R-03", "R-04", "R-08", "R-09", "R-10"]
    assert rules.status(issues) == "Blocked"


# Scorecard -------------------------------------------------------------------
from tests.conftest import STANDIN_CARRIERS  # noqa: E402


def test_scorecard_counts_passes_breaks_and_unchecked():
    b = booking([item(hs_code="6912")], total_gross_weight_kg=None)     # R-01 broken; no gross weight
    issues = rules.run_rules(b, STANDIN_CARRIERS, TODAY)
    states = {r["rule"]: r["state"] for r in rules.scorecard(b, issues)}
    assert states["R-01"] == "red"
    assert states["R-05"] == states["R-07"] == "unchecked"              # missing data is never a pass
    assert list(states) == [f"R-{n:02d}" for n in range(1, 11)]
    assert sum(s == "pass" for s in states.values()) == 7


def test_scorecard_clean_booking_passes_all_ten():
    b = booking()
    assert all(r["state"] == "pass" for r in rules.scorecard(b, rules.run_rules(b, STANDIN_CARRIERS, TODAY)))


# R-05 rules out the priority's own pick ---------------------------------------
def test_ruled_out_carrier_is_explained_with_the_pallets_to_unlock_it():
    from core.carriers import load_carriers, recommend
    # Answer key BK-043: Fastest, 830 kg on 2 pallets = 415 kg, over Carrier C's 400 kg
    b = booking(seller_priority="Fastest", destination_city="Paris", destination_country="France",
                pallets=2, total_gross_weight_kg=830)
    rec = recommend(b, load_carriers())
    assert rec.winner.option.carrier == "Carrier B"
    assert "R-05 rules out Carrier C" in rec.ruled_out and "3 pallets" in rec.ruled_out
    assert "£990.00" in rec.ruled_out


def test_nothing_ruled_out_when_the_pick_fits():
    from core.carriers import load_carriers, recommend
    assert recommend(booking(), load_carriers()).ruled_out == ""


def test_dangerous_goods_get_no_carrier():
    # Answer key BK-015 / BK-044: R-06 means reject, so no carrier is recommended
    from core.carriers import load_carriers
    from core.check import evaluate
    b = booking([item(description="Wireless earbuds with charging case, Bluetooth", hs_code="851830")])
    ev = evaluate(b, load_carriers(), date(2026, 10, 26))
    assert ev.status == "Blocked" and ev.recommendation.winner is None
    assert "R-06" in ev.recommendation.reason
    assert all(r.status == "Eliminated" for r in ev.recommendation.all_options)

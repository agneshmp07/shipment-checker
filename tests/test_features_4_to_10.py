"""Carrier headline (4), all-carrier comparison (7), carton labels (9), smarter dangerous goods (10)."""
import pytest

from core.carriers import recommend
from core.dangerous_goods import detect, possible_battery
from core.labels import carton_list, labels_pdf
from tests.conftest import STANDIN_CARRIERS
from tests.test_rules import booking, item
from ui.brand import _versus


# ---- 4. one-line reason ----
def test_headline_cheapest_one_line_with_weight_limit():
    rec = recommend(booking(seller_priority="Cheapest"), STANDIN_CARRIERS)
    assert rec.headline == ("Test C: lowest cost at £450.00 and within its weight limit "
                            "(206.7 kg per pallet, max 600 kg).")


@pytest.mark.parametrize("priority,start", [("Fastest", "Test B: fastest at 3 days"),
                                            ("Most reliable", "Test B: most reliable at 96% on time"),
                                            ("Balanced", "Test ")])
def test_headline_other_priorities(priority, start):
    assert recommend(booking(seller_priority=priority), STANDIN_CARRIERS).headline.startswith(start)


def test_headline_only_carrier():
    rec = recommend(booking(total_gross_weight_kg=1100, pallets=2), STANDIN_CARRIERS)   # 550 kg: only Test C
    assert rec.headline.startswith("Test C: the only carrier that can take 550 kg per pallet")


# ---- 7. side-by-side comparison ----
def test_versus_line():
    rec = recommend(booking(seller_priority="Cheapest"), STANDIN_CARRIERS)
    by = {r.option.carrier: r for r in rec.all_options}
    assert _versus(by["Test B"], rec.winner) == "+£300 · 4 days faster · +11 pts on time"


# ---- 9. carton labels ----
def test_labels_numbered_across_items_with_remainder():
    b = booking([item(), item(sku="BOWL-02", description="Bowl", quantity=250, units_per_carton=24, cartons=11)],
                cartons=101)
    labels = carton_list(b)
    assert len(labels) == 101 and labels[0].number == 1 and labels[-1].total == 101
    assert labels[89].sku == "MUG-01" and labels[90].sku == "BOWL-02"
    assert labels[-1].units == 10                       # 250 - 10 × 24 left for the last carton
    pdf = labels_pdf(b, "Haus & Herd GmbH")
    assert pdf.startswith(b"%PDF") and pdf.count(b"/Type /Page\n") + pdf.count(b"/Type /Page ") >= 1


def test_labels_without_cartons_still_produce_a_pdf():
    assert labels_pdf(booking([item(cartons=None)])).startswith(b"%PDF")


# ---- 10. smarter dangerous goods ----
@pytest.mark.parametrize("desc", ["Mens aftershave 100ml", "Spray paint can, red", "Vape juice 10ml",
                                  "Safety matches, 50 boxes", "Camping gas canister", "Nail polish remover"])
def test_more_names_are_blocked(desc):
    assert detect(desc, None, None)


@pytest.mark.parametrize("desc,word", [("Wireless earbuds", "earbuds"), ("Bluetooth speaker", "bluetooth"),
                                       ("Rechargeable torch", "rechargeable"), ("Kids drone", "drone")])
def test_battery_devices_need_confirming_not_blocking(desc, word):
    assert possible_battery(desc) == word and detect(desc, None, None) == []


@pytest.mark.parametrize("desc", ["Ceramic mug", "Phone case, silicone", "Battery-free LED lamp"])
def test_no_false_alarms(desc):
    assert possible_battery(desc) is None and detect(desc, None, None) == []

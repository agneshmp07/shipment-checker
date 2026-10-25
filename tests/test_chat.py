"""Phase 6: scripted chat conversation (offline parser, so it runs without an API key)."""
from datetime import date

import pytest

from core.chat_agent import ChatState, Extraction, ItemPatch, handle_message, is_complete, missing_fields
from core.offline_parser import offline_extract
from tests.conftest import STANDIN_CARRIERS

TODAY = date(2026, 10, 25)


def say(state, text):
    return handle_message(state, text, offline_extract, STANDIN_CARRIERS, TODAY)


def test_scripted_conversation_then_add_a_pallet():
    s = ChatState()

    r1 = say(s, "I'm sending 1080 mugs from Manchester to a warehouse in Frankfurt")
    b = s.booking
    assert (b.origin_city, b.destination_city, b.destination_country, b.destination_type) == \
        ("Manchester", "Frankfurt", "Germany", "Warehouse")
    assert b.items[0].quantity == 1080 and b.items[0].description == "mugs"
    # Asks only for missing things, at most 3 at a time, never for what was given
    assert len(s.last_asked) <= 3
    assert not {"origin_city", "destination_city", "destination_type", "quantity", "description"} & set(s.last_asked)
    assert "price per unit" in r1

    r2 = say(s, "They're £5 each, 12 per carton, 0.5 kg each")
    assert b.items[0].unit_price == 5 and b.items[0].units_per_carton == 12 and b.items[0].unit_weight_kg == 0.5
    assert "that's 90 cartons of mugs" in r2 and "1,080 ÷ 12" in r2          # calculated, but confirmed
    assert b.items[0].cartons is None

    r3 = say(s, "yes. HS code 691200, made in United Kingdom")
    assert b.items[0].cartons == 90 and b.items[0].hs_code == "691200"
    assert b.items[0].country_of_origin == "United Kingdom"
    assert "£5,400.00" in r3                                          # proposes declared value

    say(s, "yes, 3 pallets, 620 kg total, ready 05-12-2026")
    assert (b.cartons, b.total_declared_value, b.pallets, b.total_gross_weight_kg) == (90, 5400, 3, 620)
    assert b.ready_date == date(2026, 12, 5)

    r5 = say(s, "Cheapest. We're Northfield Goods and the slot is booked")
    assert b.seller_name == "Northfield Goods" and b.seller_priority == "Cheapest"
    assert b.delivery_appointment_booked is True
    assert is_complete(s), missing_fields(s)
    assert "booking is complete" in r5 and "Ready to ship" in r5
    assert "fixed" not in r5                    # the slot was never reported as a problem

    # Mid-conversation change
    r6 = say(s, "add a pallet")
    assert b.pallets == 4
    assert r6.startswith("Updated: pallets 3 → 4")
    assert "weight per pallet 206.7 kg → 155 kg" in r6
    assert "cost £450.00 → £600.00" in r6                              # stand-in Test C, £150/pallet
    assert "checks: all passing ✅" in r6


def test_change_that_breaks_a_rule_is_reported():
    s = ChatState()
    for msg in ["1080 mugs from Manchester to a warehouse in Frankfurt",
                "£5 each, 12 per carton, 0.5 kg each", "yes. HS code 691200, made in United Kingdom",
                "yes, 3 pallets, 620 kg total, ready 05-12-2026",
                "Cheapest. We're Northfield Goods and the slot is booked"]:
        say(s, msg)
    r = say(s, "actually the slot is not booked")
    assert "delivery slot booked → not booked" in r and "delivery appointment is not booked" in r


def test_rejects_values_outside_allowed_lists():
    s = ChatState()
    r = handle_message(s, "x", lambda *_: Extraction(origin_city="Glasgow", destination_city="Madrid"),
                       STANDIN_CARRIERS, TODAY)
    assert "Glasgow" in r and "London, Manchester, Birmingham, Leeds" in r
    assert "Madrid" in r and s.booking.origin_city is None


def test_rejected_proposal_is_asked_directly():
    s = ChatState()
    handle_message(s, "x", lambda *_: Extraction(items=[ItemPatch(description="mugs", quantity=1080,
                                                                  units_per_carton=12)]),
                   STANDIN_CARRIERS, TODAY)
    assert s.pending and s.pending[0].value == 90
    r = handle_message(s, "no", lambda *_: Extraction(confirms_proposal=False), STANDIN_CARRIERS, TODAY)
    assert s.booking.items[0].cartons is None and "how many cartons" in r


def test_hs_code_not_nagged_forever():
    s = ChatState()
    ex = lambda *_: Extraction()
    handle_message(s, "x", lambda *_: Extraction(items=[ItemPatch(description="mugs", quantity=10)]),
                   STANDIN_CARRIERS, TODAY)
    keys = []
    for _ in range(12):
        handle_message(s, "don't know", ex, STANDIN_CARRIERS, TODAY)
        keys.append(tuple(s.last_asked))
    assert sum("hs_code" in k for k in keys) <= 2


@pytest.mark.parametrize("text,field,value", [
    ("ready tomorrow", "ready_date", "26-10-2026"),
    ("we need it fast", "seller_priority", "Fastest"),
    ("going to an office in Lyon", "destination_type", "Business address"),
    ("total value £2,400", "total_declared_value", 2400),
    ("2 pallets", "pallets", 2),
])
def test_offline_parser_phrases(text, field, value):
    assert getattr(offline_extract(text, ChatState(), TODAY), field) == value



def test_dont_know_hs_code_stops_asking_and_completes():
    s = ChatState()
    r1 = say(s, "1080 mugs from Manchester to a warehouse in Frankfurt")
    r2 = say(s, "£5 each, 12 per carton, 0.5 kg each, made in United Kingdom, no idea what the HS code is")
    assert "leave the HS code blank" in r2 and "HS code" not in r2.split("Could you tell me")[-1]
    say(s, "yes, 3 pallets, 620 kg total, ready 05-12-2026")
    say(s, "Cheapest. We're Northfield Goods and the slot is booked")
    r = say(s, "yes")                                  # accept the calculated totals
    assert is_complete(s) and "must be fixed before it can ship" in r


def test_two_products_questions_and_summary_name_the_product():
    s = ChatState()
    handle_message(s, "x", lambda *_: Extraction(origin_city="London", destination_city="Paris",
                                                  destination_type="Business address",
                                                  items=[ItemPatch(description="mugs", quantity=300),
                                                         ItemPatch(description="plates", quantity=200)]),
                   STANDIN_CARRIERS, TODAY)
    q = s.messages[-1]["content"]
    assert "For the mugs, could you tell me" in q and q.count("for mugs") == 0
    r = handle_message(s, "x", lambda *_: Extraction(items=[ItemPatch(match="mugs", unit_price=6),
                                                            ItemPatch(match="plates", unit_price=4)]),
                       STANDIN_CARRIERS, TODAY)
    assert "mugs £6.00 each" in r and "plates £4.00 each" in r
    r = handle_message(s, "x", lambda *_: Extraction(remove_items=["plates"]), STANDIN_CARRIERS, TODAY)
    assert "removed plates" in r and len(s.booking.items) == 1

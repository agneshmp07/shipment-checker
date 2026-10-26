"""'What we found' pop-up content, and the pop-up on the upload page."""
import json
from datetime import date
from pathlib import Path

from streamlit.testing.v1 import AppTest

from core.check import evaluate
from core.findings import findings
from tests.conftest import STANDIN_CARRIERS, upload_file
from tests.fixtures.make_planted_mistakes import OUT, build
from tests.test_rules import booking, item

TODAY = date(2026, 10, 25)
ROOT = Path(__file__).resolve().parent.parent


def f_for(b):
    return findings(evaluate(b, STANDIN_CARRIERS, TODAY))


def test_root_cause_gives_fix_and_confident_recommendation():
    f = f_for(booking([item(cartons=80)], cartons=90))
    assert f.wrong[0].startswith("Must fix — ") and "960 units" in " ".join(f.wrong)
    assert f.fix == ["Set cartons for MUG-01 to 90."]
    assert f.recommend[0].startswith("Most likely typo: cartons for MUG-01 should be 90, not 80 (we're confident")


def test_single_problem_says_what_happens_after():
    f = f_for(booking(pallets=1, total_gross_weight_kg=900))       # 900 kg on one pallet: too heavy
    assert len(f.wrong) == 1 and "at least 2 pallets" in f.fix[0]
    assert f.recommend == ["Once you've done this, the booking is ready to ship."]


def test_several_problems_say_where_to_start():
    f = f_for(booking([item(hs_code=None, country_of_origin=None)], delivery_appointment_booked=False))
    assert f.recommend[0].startswith("Start with “HS code missing or not valid” — it stops the shipment")
    assert "Country of origin missing" in f.recommend[0]


def test_clean_booking_has_nothing():
    f = f_for(booking())
    assert f.wrong == f.fix == f.recommend == []


def test_popup_opens_after_upload_and_open_selects_booking(tmp_path, monkeypatch):
    path = tmp_path / "carriers.json"
    path.write_text(json.dumps([c.model_dump() for c in STANDIN_CARRIERS]))
    monkeypatch.setenv("SHIPMENT_CARRIERS_PATH", str(path))
    build()
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60).run()
    at.switch_page("app_pages/upload_file.py").run()
    at.session_state["show_findings"] = True                  # what a new upload sets
    upload_file(at, OUT)
    assert not at.exception
    labels = [b.label for b in at.button]
    assert "Fix BK-107" in labels and any(l.startswith("See what's wrong (") for l in labels)
    text = " ".join(m.value for m in at.markdown)
    assert "**What's wrong**" in text and "**Our recommendation**" in text
    next(b for b in at.button if b.key == "find-open-BK-107").click().run()      # "View details"
    assert not at.exception and at.session_state["focus_booking"] == "BK-107"
    banners = [h.proto.body for h in at.get("html") if 'class="sc-banner' in h.proto.body]
    assert banners and ">BK-107" in banners[0]


def test_repeated_problem_is_one_line():
    b = booking([item(hs_code=None), item(sku="MUG-02", hs_code="6912")],
                cartons=180, total_declared_value=10800, total_gross_weight_kg=1300, pallets=3)
    f = f_for(b)
    assert f.recommend == ["Fix the 2 HS codes — it stops the shipment. Then the booking is ready to ship."]

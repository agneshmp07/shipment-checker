"""Phase 8: Trade Connect directory, filters, pre-checked badge, connect form."""
import json
from datetime import date
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from core.check import evaluate
from core.diagnosis import apply_fix
from core.excel_loader import load_workbook
from core.trade_connect import filter_directory, load_directory, prechecked_sellers, validate_request
from tests.conftest import STANDIN_CARRIERS
from tests.fixtures.make_planted_mistakes import OUT, build

TODAY = date(2026, 10, 25)
ROOT = Path(__file__).resolve().parent.parent


def test_directory_size_and_countries():
    d = load_directory()
    assert 10 <= len(d) <= 15
    assert {e.country for e in d} == {"United Kingdom", "Germany", "France", "Netherlands"}
    assert {e.role for e in d} == {"Buyer", "Seller"}


def test_filters_and_search():
    d = load_directory()
    de_buyers = filter_directory(d, ["Germany"], "Buyer")
    assert de_buyers and all(e.country == "Germany" and e.role == "Buyer" for e in de_buyers)
    ceramics = filter_directory(d, categories=["Ceramics"])
    assert all("Ceramics" in e.categories for e in ceramics)
    assert [e.name for e in filter_directory(d, query="rotterdam")] == ["Maaspoort Distributie"]
    assert filter_directory(d, ["France"], "Seller", ["Ceramics"]) == []


def test_badge_only_when_all_bookings_ready():
    build()
    bookings = load_workbook(OUT).bookings
    evals = [evaluate(b, STANDIN_CARRIERS, TODAY) for b in bookings]
    pre = prechecked_sellers(evals)
    assert "thread & co" in pre                     # BK-102 clean
    assert "northfield goods" not in pre            # BK-101 ready but BK-107 blocked
    bk107 = next(b for b in bookings if b.booking_id == "BK-107")
    apply_fix(bk107, {"target": "item", "sku": "MUG-01", "field": "cartons", "value": 90.0})
    evals = [evaluate(b, STANDIN_CARRIERS, TODAY) for b in bookings]
    assert "northfield goods" in prechecked_sellers(evals)


@pytest.mark.parametrize("name,email,msg,ok", [
    ("Sam", "sam@example.com", "We sell ceramic mugs.", True),
    ("", "sam@example.com", "We sell ceramic mugs.", False),
    ("Sam", "not-an-email", "We sell ceramic mugs.", False),
    ("Sam", "sam@example.com", "hi", False),
])
def test_validate_request(name, email, msg, ok):
    assert (validate_request(name, email, msg) == []) is ok


def test_page_renders_with_badges_after_upload(tmp_path, monkeypatch):
    path = tmp_path / "carriers.json"
    path.write_text(json.dumps([c.model_dump() for c in STANDIN_CARRIERS]))
    monkeypatch.setenv("SHIPMENT_CARRIERS_PATH", str(path))
    build()
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30)
    at.run()
    at.switch_page("app_pages/trade_connect.py").run()
    assert not at.exception
    at.session_state["upload_bookings"] = load_workbook(OUT).bookings
    at.run()
    assert not at.exception
    text = " ".join(m.value for m in at.markdown)
    assert "**Thread & Co** :green-badge[Pre-checked shipper ✅]" in text
    assert "**Northfield Goods** :green-badge" not in text

"""The pre-flight gate: documents unlock only when no Red rule is broken and every rule was checked."""
import json
from datetime import date
from pathlib import Path

from streamlit.testing.v1 import AppTest

from core.check import evaluate
from tests.conftest import STANDIN_CARRIERS, upload_file
from tests.fixtures.make_planted_mistakes import OUT, build
from tests.test_rules import booking, item
from ui.preflight import gate

ROOT = Path(__file__).resolve().parent.parent


def ev(b):
    return evaluate(b, STANDIN_CARRIERS, date.today())


def test_clean_booking_clears():
    ok, reasons = gate(ev(booking([item()])))
    assert ok and reasons == []


def test_red_rule_holds_the_gate():
    ok, reasons = gate(ev(booking([item(hs_code="123456")])))
    assert not ok and any(r.startswith("R-01") for r in reasons)


def test_missing_data_never_clears():
    ok, reasons = gate(ev(booking([item(quantity=None)])))
    assert not ok and reasons


def _page(tmp_path, monkeypatch, bid):
    path = tmp_path / "carriers.json"
    path.write_text(json.dumps([c.model_dump() for c in STANDIN_CARRIERS]))
    monkeypatch.setenv("SHIPMENT_CARRIERS_PATH", str(path))
    build()
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60).run()
    at.switch_page("app_pages/upload_file.py").run()
    at = upload_file(at, OUT)
    at.session_state["focus_booking"] = bid
    return at.run()


def _first(at, status):
    return next(b.booking_id for b in at.session_state["upload_bookings"] if ev(b).status == status)


def test_blocked_booking_locks_labels_and_invoice(tmp_path, monkeypatch):
    at = _page(tmp_path, monkeypatch, None)
    at = _page(tmp_path, monkeypatch, _first(at, "Blocked"))
    assert not at.exception
    locked = [e.value for e in at.error if "pre-flight not cleared" in e.value]
    assert any("confirmation and carton labels" in v for v in locked)
    assert any("commercial invoice" in v for v in locked)
    labels = [d.proto.label for d in at.get("download_button")]
    assert "Pre-flight report" in labels
    assert not {"Carton labels (PDF)", "Invoice (PDF)", "Invoice (Excel)"} & set(labels)


def test_cleared_booking_unlocks_documents(tmp_path, monkeypatch):
    at = _page(tmp_path, monkeypatch, None)
    at = _page(tmp_path, monkeypatch, _first(at, "Ready"))
    assert not at.exception
    assert not [e for e in at.error if "pre-flight not cleared" in e.value]
    labels = {d.proto.label for d in at.get("download_button")}
    assert {"Carton labels (PDF)", "Invoice (PDF)"} <= labels

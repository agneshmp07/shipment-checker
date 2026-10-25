"""Headless smoke test of the upload page with the planted-mistakes fixture."""
import json
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from tests.conftest import STANDIN_CARRIERS, upload_file
from tests.fixtures.make_planted_mistakes import EXPECTED, OUT, build

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def app(tmp_path, monkeypatch):
    path = tmp_path / "carriers.json"
    path.write_text(json.dumps([c.model_dump() for c in STANDIN_CARRIERS]))
    monkeypatch.setenv("SHIPMENT_CARRIERS_PATH", str(path))
    build()
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30)
    at.run()
    return at


def test_home_renders(app):
    assert not app.exception
    labels = [b.label for b in app.button]
    assert "Book by chat or voice" in labels and "See a 30-second demo" not in labels


def test_upload_sample_shows_every_booking(app):
    app.switch_page("app_pages/upload_file.py").run()
    assert not app.exception
    upload_file(app, OUT)
    assert not app.exception
    table = app.dataframe[0].value
    assert set(table["Booking"]) == set(EXPECTED)
    for _, row in table.iterrows():
        broken = set() if row["Rules broken"] == "—" else set(row["Rules broken"].split(", "))
        expected = {"Input" if r == "DATA" else r for r in EXPECTED[row["Booking"]]}
        assert broken == expected, row["Booking"]
    metrics = {m.label: m.value for m in app.metric}
    assert metrics["Bookings"] == "14" and metrics["🟢 Ready to ship"] == "3"


def test_no_sample_shortcuts_on_upload_page(app):
    app.switch_page("app_pages/upload_file.py").run()
    labels = [b.label for b in app.button]
    assert not any("sample" in (l or "").lower() for l in labels)

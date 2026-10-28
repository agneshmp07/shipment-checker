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
    red_rules = {"R-01", "R-02", "R-03", "R-04", "R-05", "R-06", "DATA"}
    for _, row in table.iterrows():
        rules = EXPECTED[row["Booking"]]
        want = "Ready to ship" if not rules else "Blocked" if rules & red_rules else "Ready with warnings"
        assert row["Status"].endswith(want), row["Booking"]
    assert list(table.columns) == ["Booking", "Status", "Rules passed", "Broke", "Route", "Best carrier", "Seller"]
    for _, row in table.iterrows():                       # the rules each booking broke, and its score
        broke = sorted(r for r in EXPECTED[row["Booking"]] if r != "DATA")
        assert row["Broke"] == (", ".join(broke) or "—"), row["Booking"]
        assert int(row["Rules passed"].split("/")[0]) <= 10 - len(broke)
    grid = app.dataframe[1].value                         # the 10-rule grid tab
    assert list(grid.columns) == ["Booking", "Passed"] + [f"R-{n:02d}" for n in range(1, 11)]
    assert set(grid.iloc[0, 2:]) <= {"✓", "✕", "!", "–"}
    tiles = dict(b.label.rsplit(": ", 1) for b in app.button if (b.key or "").startswith("tilebtn-"))
    assert tiles == {"Can't ship yet": "9", "Warnings": "2", "Ready to ship": "3"}


def test_tapping_a_status_card_filters_the_table(app):
    app.switch_page("app_pages/upload_file.py").run()
    upload_file(app, OUT)
    app.button(key="tilebtn-Ready").click().run()
    assert not app.exception
    table = app.dataframe[0].value
    assert len(table) == 3 and all(s.endswith("Ready to ship") for s in table["Status"])
    assert len(app.dataframe[1].value) == 3                # the 10-rule grid follows the filter
    app.button(key="tilebtn-Ready").click().run()          # tap again: everything is back
    assert len(app.dataframe[0].value) == 14
    app.button(key="tilebtn-Blocked").click().run()
    assert len(app.dataframe[0].value) == 9
    app.button(key="tile-clear").click().run()             # 'Show all'
    assert len(app.dataframe[0].value) == 14


def test_no_sample_shortcuts_on_upload_page(app):
    app.switch_page("app_pages/upload_file.py").run()
    labels = [b.label for b in app.button]
    assert not any("sample" in (l or "").lower() for l in labels)


def test_home_is_short_with_a_guide(app):
    md = " ".join(m.value for m in app.markdown)
    assert "Key terms" not in md and "Everything in Oops-Proof" not in md and "How it works" not in md
    app.button(key="home-guide").click().run()
    assert not app.exception
    assert [t.label for t in app.tabs][:4] == ["Quick start", "Sections", "The 10 rules", "Key terms"]


def test_pages_have_a_guide_button_not_a_how_to_box(app):
    app.switch_page("app_pages/upload_file.py").run()
    assert not [e for e in app.expander if e.label == "How to use this page"]
    app.button(key="guide-upload").click().run()
    assert not app.exception
    assert any("Checking a bookings file" in m.value for m in app.markdown)

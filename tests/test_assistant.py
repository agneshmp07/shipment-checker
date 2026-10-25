"""The 'Ask AI' helper: grounded context, built-in answers, and the popover on a page."""
import json
from datetime import date
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from core import assistant, llm
from core.check import evaluate
from core.excel_loader import load_workbook
from tests.conftest import STANDIN_CARRIERS
from tests.fixtures.make_planted_mistakes import OUT, build

TODAY = date(2026, 10, 25)
ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def evals():
    build()
    return {b.booking_id: evaluate(b, STANDIN_CARRIERS, TODAY) for b in load_workbook(OUT).bookings}


def test_offline_why_blocked_names_root_cause(evals):
    text = assistant.offline_answer("why is BK-107 blocked?", None, None, list(evals.values()))
    assert "BK-107" in text and "cartons for MUG-01 should be 90" in text


def test_offline_uses_booking_on_screen(evals):
    text = assistant.offline_answer("what's wrong with this booking", evals["BK-106"], None, [])
    assert "declared value" in text.lower() and "£3,000.00" in text


def test_offline_clean_booking_and_unknown_id(evals):
    assert "passes all 10 checks" in assistant.offline_answer("why BK-101?", None, None, list(evals.values()))
    assert "can't find booking BK-999" in assistant.offline_answer("why is bk-999 blocked", None, None, [])


@pytest.mark.parametrize("q,expect", [("what is an HS code?", "international customs code"),
                                      ("how do I upload my excel", "Browse files"),
                                      ("what's a pallet", "wooden platform"),
                                      ("hello", "I can help with")])
def test_offline_general(q, expect):
    assert expect in assistant.offline_answer(q, None, None, [])


def test_context_contains_real_numbers(evals):
    ctx = assistant.build_context("Check a file", evals["BK-107"], None, list(evals.values()))
    assert "Booking the user is looking at" in ctx and "960 units" in ctx and "Root cause" in ctx
    assert "14 bookings - 3 ready, 2 with warnings, 9 blocked" in ctx


def test_answer_uses_llm_with_context(monkeypatch, evals):
    seen = {}

    def fake_text(system, messages, **_):
        seen["system"], seen["messages"] = system, messages
        return "BK-107 has a carton typo."
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    monkeypatch.setattr(llm, "llm_text", fake_text)
    reply, source = assistant.answer("why blocked?", [], "Check a file", evals["BK-107"], None, [])
    assert (reply, source) == ("BK-107 has a carton typo.", "ai")
    assert "never by you" in seen["system"] and "960 units" in seen["messages"][-1]["content"]


def test_answer_falls_back_when_llm_fails(monkeypatch, evals):
    def boom(*a, **k):
        raise llm.LLMUnavailable("down")
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    monkeypatch.setattr(llm, "llm_text", boom)
    reply, source = assistant.answer("why is BK-107 blocked?", [], "Home", None, None, list(evals.values()))
    assert source == "built-in" and "MUG-01" in reply


def test_ask_ai_on_a_page(tmp_path, monkeypatch):
    path = tmp_path / "carriers.json"
    path.write_text(json.dumps([c.model_dump() for c in STANDIN_CARRIERS]))
    monkeypatch.setenv("SHIPMENT_CARRIERS_PATH", str(path))
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    at.text_input[0].set_value("What is an HS code?")
    next(b for b in at.button if b.label == "Ask").click().run()
    assert not at.exception
    assert at.session_state["ai_history"][-1]["content"].startswith("An **HS code**")


def test_context_marks_unfinished_chat_booking(evals):
    ctx = assistant.build_context("Book by chat", None, evals["BK-101"], [], ["how many pallets"])
    assert "not finished yet" in ctx and "how many pallets" in ctx

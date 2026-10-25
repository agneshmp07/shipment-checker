"""LLM layer with a fake client (no network), and the chat page without an API key."""
import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import anthropic
import httpx
import pytest
from streamlit.testing.v1 import AppTest

from core import llm
from core.chat_agent import ChatState, Extraction, ItemPatch
from tests.conftest import STANDIN_CARRIERS

TODAY = date(2026, 10, 25)
ROOT = Path(__file__).resolve().parent.parent


class FakeMessages:
    def __init__(self, outputs):
        self.outputs, self.calls = list(outputs), []

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        out = self.outputs.pop(0)
        if isinstance(out, Exception):
            raise out
        return SimpleNamespace(stop_reason="end_turn", parsed_output=out)


def fake_client(monkeypatch, outputs):
    msgs = FakeMessages(outputs)
    client = SimpleNamespace(messages=msgs, beta=SimpleNamespace(messages=msgs))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(llm, "_client", lambda key: client)
    return msgs


def test_no_key_raises_unavailable(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(llm.LLMUnavailable):
        llm.llm_extract("hi", ChatState(), TODAY)


def test_success_uses_structured_output_and_fallbacks(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)
    want = Extraction(origin_city="Manchester", items=[ItemPatch(description="mugs", quantity=1080)])
    msgs = fake_client(monkeypatch, [want])
    assert llm.llm_extract("1080 mugs from Manchester", ChatState(), TODAY) == want
    call = msgs.calls[0]
    assert call["output_format"] is Extraction and call["model"] == "claude-opus-5-5"
    assert call["fallbacks"] == "default" and "25-10-2026" in call["messages"][0]["content"]


def test_invalid_json_retried_once_then_unavailable(monkeypatch):
    msgs = fake_client(monkeypatch, [ValueError("bad json"), ValueError("bad json")])
    with pytest.raises(llm.LLMUnavailable):
        llm.llm_extract("hi", ChatState(), TODAY)
    assert len(msgs.calls) == 2


def test_invalid_then_valid(monkeypatch):
    fake_client(monkeypatch, [ValueError("bad json"), Extraction(pallets=3)])
    assert llm.llm_extract("3 pallets", ChatState(), TODAY).pallets == 3


def test_api_error_is_unavailable(monkeypatch):
    err = anthropic.APIConnectionError(request=httpx.Request("POST", "https://api.anthropic.com"))
    fake_client(monkeypatch, [err])
    with pytest.raises(llm.LLMUnavailable):
        llm.llm_extract("hi", ChatState(), TODAY)


def test_other_model_skips_fallbacks(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-haiku-5-5")
    msgs = fake_client(monkeypatch, [Extraction()])
    llm.llm_extract("hi", ChatState(), TODAY)
    assert "fallbacks" not in msgs.calls[0] and msgs.calls[0]["model"] == "claude-haiku-5-5"


def test_phrase_and_dg_fail_quietly(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert llm.llm_phrase(ChatState(), [], "Q?") is None
    assert llm.llm_dg_second_opinion([("X", "earbuds")]) == []


# ---- Chat page end to end, no API key -------------------------------------------

@pytest.fixture
def chat_app(tmp_path, monkeypatch):
    path = tmp_path / "carriers.json"
    path.write_text(json.dumps([c.model_dump() for c in STANDIN_CARRIERS]))
    monkeypatch.setenv("SHIPMENT_CARRIERS_PATH", str(path))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30)
    at.run()
    at.switch_page("app_pages/chat_booking.py").run()
    return at


def test_chat_page_without_key_completes_booking(chat_app):
    at = chat_app
    assert not at.exception
    assert any("AI assistant is unavailable" in i.value for i in at.info)
    for msg in ["I'm sending 1080 mugs from Manchester to a warehouse in Frankfurt",
                "They're £5 each, 12 per carton, 0.5 kg each",
                "yes. HS code 691200, made in United Kingdom",
                "yes, 3 pallets, 620 kg total, ready 05-12-2026",
                "Cheapest. We're Northfield Goods and the slot is booked",
                "add a pallet"]:
        at.chat_input[0].set_value(msg).run()
        assert not at.exception, msg
    texts = [m.value for m in at.markdown]
    assert any(t.startswith("Updated: pallets 3 → 4") for t in texts)
    assert any(b.label == "Confirm booking" for b in at.button)      # results + confirm shown

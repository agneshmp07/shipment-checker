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


# ---- Gemini provider (fake client, no network) --------------------------------------

from google.genai import errors as genai_errors


class FakeGeminiModels:
    def __init__(self, outputs):
        self.outputs, self.calls = list(outputs), []

    def generate_content(self, model, contents, config):
        self.calls.append({"model": model, "contents": contents, "config": config})
        out = self.outputs.pop(0)
        if isinstance(out, Exception):
            raise out
        return SimpleNamespace(text=out)


def fake_gemini(monkeypatch, outputs):
    models = FakeGeminiModels(outputs)
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setattr(llm, "_gemini_client", lambda key: SimpleNamespace(models=models))
    return models


def test_gemini_selected_when_only_gemini_key(monkeypatch):
    want = Extraction(origin_city="Leeds", items=[ItemPatch(description="mugs", quantity=10)])
    calls = fake_gemini(monkeypatch, [want.model_dump_json()])
    assert llm.provider() == "gemini" and llm.available()
    assert llm.llm_extract("10 mugs from Leeds", ChatState(), TODAY) == want
    call = calls.calls[0]
    assert call["model"] == "gemini-flash-latest"
    cfg = call["config"]
    assert cfg.response_mime_type == "application/json"
    assert "$ref" not in json.dumps(cfg.response_json_schema)          # nested models inlined
    assert "items" in cfg.response_json_schema["properties"]
    assert "Allowed values" in cfg.system_instruction and "25-10-2026" in call["contents"]


def test_anthropic_preferred_when_both_keys(monkeypatch):
    fake_gemini(monkeypatch, [])
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    assert llm.provider() == "anthropic"


def test_gemini_unknown_model_falls_back(monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "gemini-does-not-exist")
    not_found = genai_errors.ClientError(404, {"error": {"code": 404, "message": "not found", "status": "NOT_FOUND"}})
    calls = fake_gemini(monkeypatch, [not_found, Extraction(pallets=2).model_dump_json()])
    assert llm.llm_extract("2 pallets", ChatState(), TODAY).pallets == 2
    assert [c["model"] for c in calls.calls] == ["gemini-does-not-exist", "gemini-2.5-flash"]


def test_gemini_quota_error_is_unavailable(monkeypatch):
    quota = genai_errors.ClientError(429, {"error": {"code": 429, "message": "quota", "status": "RESOURCE_EXHAUSTED"}})
    fake_gemini(monkeypatch, [quota])
    with pytest.raises(llm.LLMUnavailable):
        llm.llm_extract("hi", ChatState(), TODAY)


def test_gemini_bad_json_retried_then_unavailable(monkeypatch):
    calls = fake_gemini(monkeypatch, ["not json", '{"pallets": "three"}'])
    with pytest.raises(llm.LLMUnavailable):
        llm.llm_extract("hi", ChatState(), TODAY)
    assert len(calls.calls) == 2


def test_gemini_phrase_and_dg(monkeypatch):
    fake_gemini(monkeypatch, ['{"text": "Lovely! How many pallets?"}',
                              '{"hints": [{"sku": "EB-1", "reason": "earbuds contain a lithium battery"}]}'])
    assert llm.llm_phrase(ChatState(), [], "How many pallets?") == "Lovely! How many pallets?"
    assert llm.llm_dg_second_opinion([("EB-1", "Wireless earbuds")])[0].sku == "EB-1"


def test_gemini_thinking_falls_back_when_unsupported(monkeypatch):
    llm._thinking_mode_for.clear()
    bad = genai_errors.ClientError(400, {"error": {"code": 400, "message": "thinking_level not supported",
                                                   "status": "INVALID_ARGUMENT"}})
    calls = fake_gemini(monkeypatch, [bad, Extraction(pallets=1).model_dump_json(),
                                      Extraction(pallets=2).model_dump_json()])
    assert llm.llm_extract("1 pallet", ChatState(), TODAY).pallets == 1
    first, second = calls.calls[0]["config"].thinking_config, calls.calls[1]["config"].thinking_config
    assert first.thinking_level is not None and second.thinking_budget == 0
    llm.llm_extract("2 pallets", ChatState(), TODAY)                    # remembered: no failed attempt
    assert calls.calls[2]["config"].thinking_config.thinking_budget == 0


def test_gemini_timeouts_per_purpose(monkeypatch):
    llm._thinking_mode_for.clear()
    calls = fake_gemini(monkeypatch, [Extraction().model_dump_json(), '{"text": "Q?"}'])
    llm.llm_extract("hi", ChatState(), TODAY)
    llm.llm_phrase(ChatState(), [], "Q?")
    assert [c["config"].http_options.timeout for c in calls.calls] == [25000, 8000]

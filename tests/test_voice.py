"""Voice: transcription and text-to-speech via Gemini (fake client), and speech text cleaning."""
import io
import wave
from types import SimpleNamespace

import pytest

from core import llm
from ui.voice import speech_text


class FakeModels:
    def __init__(self, outputs):
        self.outputs, self.calls = list(outputs), []

    def generate_content(self, model, contents, config):
        self.calls.append({"model": model, "contents": contents, "config": config})
        out = self.outputs.pop(0)
        if isinstance(out, Exception):
            raise out
        return out


def fake(monkeypatch, outputs):
    models = FakeModels(outputs)
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    monkeypatch.setattr(llm, "_gemini_client", lambda key: SimpleNamespace(models=models))
    llm._thinking_mode_for.clear()
    return models


def test_voice_needs_gemini_key(monkeypatch):
    assert not llm.voice_available()
    with pytest.raises(llm.LLMUnavailable):
        llm.transcribe(b"RIFF....", "audio/wav")
    assert llm.speak("hello") is None


def test_transcribe_sends_audio_part(monkeypatch):
    m = fake(monkeypatch, [SimpleNamespace(text='"I\'m sending 1080 mugs from Manchester"\n')])
    assert llm.transcribe(b"RIFFdata", "audio/wav") == "I'm sending 1080 mugs from Manchester"
    part, instruction = m.calls[0]["contents"]
    assert part.inline_data.mime_type == "audio/wav" and part.inline_data.data == b"RIFFdata"
    assert "digits" in m.calls[0]["config"].system_instruction


def test_transcribe_works_even_when_claude_is_main_provider(monkeypatch):
    m = fake(monkeypatch, [SimpleNamespace(text="hello")])
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    assert llm.transcribe(b"x") == "hello"
    assert m.calls[0]["model"] == "gemini-flash-latest"          # Gemini model, not the Claude one


def _tts_response(data, mime):
    blob = SimpleNamespace(data=data, mime_type=mime)
    return SimpleNamespace(candidates=[SimpleNamespace(content=SimpleNamespace(parts=[SimpleNamespace(inline_data=blob)]))])


def test_speak_wraps_pcm_as_wav(monkeypatch):
    pcm = b"\x00\x01" * 2400
    m = fake(monkeypatch, [_tts_response(pcm, "audio/L16;codec=pcm;rate=24000")])
    wav = llm.speak("How many pallets?")
    with wave.open(io.BytesIO(wav)) as w:
        assert (w.getframerate(), w.getnchannels(), w.getsampwidth(), w.getnframes()) == (24000, 1, 2, 2400)
    cfg = m.calls[0]["config"]
    assert cfg.response_modalities == ["AUDIO"] and m.calls[0]["model"] == "gemini-2.5-flash-preview-tts"
    assert cfg.speech_config.voice_config.prebuilt_voice_config.voice_name == "Kore"


def test_speak_returns_none_on_any_error(monkeypatch):
    fake(monkeypatch, [RuntimeError("model not found")])
    assert llm.speak("hi") is None


def test_speech_text_skips_change_log_and_markup():
    reply = ("Updated: pallets 3 → 4 · cost £540.00 → £720.00 · checks: all passing ✅\n\n"
             "Your booking is complete — 🟢 **Ready to ship**. :red-badge[Red] issues: none.")
    text = speech_text(reply)
    assert not text.startswith("Updated") and "**" not in text and "🟢" not in text
    assert "Ready to ship" in text and "Red issues" in text

"""Voice helpers: transcribe a recording, and read a reply aloud."""
from __future__ import annotations

import json
import re

import streamlit as st

from core import llm


def speech_text(reply: str) -> str:
    """The part of a reply worth hearing: drop the 'Updated: …' change log, markdown and emoji."""
    parts = [p for p in reply.split("\n\n") if not p.startswith("Updated:")] or [reply]
    text = " ".join(parts)
    text = re.sub(r"[*_`#>]|:\w+-badge\[([^\]]*)\]|:material/\w+:", r"\1", text)
    text = re.sub(r"[\U0001F300-\U0001FAFF☀-➿]", "", text)          # emoji
    text = text.replace("→", " to ").replace("£", " pounds ").replace("÷", " divided by ")
    return re.sub(r"\s+", " ", text).strip()[:600]


def transcribe(recording) -> str | None:
    """Recording (UploadedFile, audio/wav) -> text, or None with a message if it fails."""
    try:
        text = llm.transcribe(recording.getvalue(), recording.type or "audio/wav")
    except (llm.LLMUnavailable, llm.InvalidOutput) as e:
        st.toast(f"Couldn't understand the recording ({str(e)[:80]}). Please type instead.",
                 icon=":material/mic_off:")
        return None
    if not text:
        st.toast("I didn't catch any words — try again a little closer to the mic.", icon=":material/mic_off:")
        return None
    return text


def say(reply: str):
    """Read a reply aloud: Gemini's voice if available, otherwise the browser's built-in voice."""
    text = speech_text(reply)
    if not text:
        return
    audio = llm.speak(text)
    if audio:
        st.audio(audio, format="audio/wav", autoplay=True)
        return
    st.html(f"""<script>
      (function() {{
        var s = window.parent && window.parent.speechSynthesis ? window.parent.speechSynthesis : window.speechSynthesis;
        if (!s) return;
        s.cancel();
        var u = new SpeechSynthesisUtterance({json.dumps(text)});
        u.lang = "en-GB"; u.rate = 1.0;
        s.speak(u);
      }})();
    </script>""", unsafe_allow_javascript=True)

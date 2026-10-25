"""'Ask AI' button shown at the top of every page."""
from __future__ import annotations

from datetime import date

import streamlit as st

from core import assistant, llm
from core.chat_agent import LABELS, ChatState, missing_fields
from core.check import evaluate
from ui.results import get_carriers
from ui.voice import say, transcribe

SUGGESTIONS = ["Why is my booking blocked?", "How do I fix it?", "Which carrier and why?",
               "What is an HS code?", "How do I upload a file?"]


def _gather():
    """The evaluations the assistant may talk about: the booking on screen, the chat, the upload."""
    carriers, today = get_carriers(), date.today()
    page_focus = st.session_state.get("assistant_focus")
    focus = page_focus[1] if page_focus and page_focus[0] == st.session_state.get("current_page") else None
    chat_ev = None
    chat: ChatState | None = st.session_state.get("chat")
    if chat is not None and (chat.booking.items or chat.booking.destination_city):
        chat_ev = evaluate(chat.booking, carriers, today)
    uploads = [evaluate(b, carriers, today) for b in st.session_state.get("upload_bookings") or []]
    if focus is not None:   # re-evaluate so it reflects any fix applied since it was shown
        focus = evaluate(focus.booking, carriers, today)
    chat_missing = [LABELS[f] for _, f, _ in missing_fields(chat)] if chat_ev is not None else []
    return focus, chat_ev, uploads, chat_missing


def ask(question: str, page: str):
    history = st.session_state.setdefault("ai_history", [])
    focus, chat_ev, uploads, chat_missing = _gather()
    with st.spinner("Thinking…"):
        reply, source = assistant.answer(question, history, page, focus, chat_ev, uploads, chat_missing)
    history += [{"role": "user", "content": question}, {"role": "assistant", "content": reply, "source": source}]


def _pick_suggestion():
    st.session_state.ai_pending = st.session_state.ai_suggestion
    st.session_state.ai_suggestion = None


def render_ask_ai(page: str):
    with st.container(horizontal=True, horizontal_alignment="right"):
        with st.popover("Ask AI", icon=":material/auto_awesome:", type="primary", key="ask_ai_popover"):
            st.markdown("**ShipCheck assistant**")
            st.caption("Ask me anything about your shipment, a booking on screen, or how to use ShipCheck.")
            pending = st.session_state.pop("ai_pending", None)
            with st.form("ask_ai_form", clear_on_submit=True, border=False):
                q = st.text_input("Your question", placeholder="e.g. Why is BK-107 blocked?",
                                  label_visibility="collapsed")
                if st.form_submit_button("Ask", icon=":material/send:", type="primary"):
                    pending = q.strip() or pending
            spoken = False
            if llm.voice_available():
                rec = st.audio_input("Or ask by voice", key="ai_voice")
                if rec is not None and st.session_state.get("ai_voice_seen") != rec.file_id:
                    st.session_state.ai_voice_seen = rec.file_id          # handle each recording once
                    with st.spinner("Listening…"):
                        heard = transcribe(rec)
                    if heard:
                        pending, spoken = heard, True
            speak = st.toggle("Speak answers", key="ai_speak", value=False)
            if pending:
                ask(pending, page)
                if spoken or speak:
                    say(st.session_state.ai_history[-1]["content"])
            history = st.session_state.get("ai_history", [])
            if not history:
                st.pills("Try", SUGGESTIONS, key="ai_suggestion", on_change=_pick_suggestion,
                         label_visibility="collapsed")
            if history:
                pairs = list(zip(history[::2], history[1::2]))
                with st.container(height=360, border=False):
                    for question, reply in reversed(pairs[-6:]):     # newest pair first, under the input
                        with st.chat_message("user", avatar=":material/person:"):
                            st.markdown(question["content"])
                        with st.chat_message("assistant", avatar=":material/auto_awesome:"):
                            st.markdown(reply["content"])
            if history and st.button("Clear conversation", type="tertiary", icon=":material/delete_sweep:"):
                st.session_state.ai_history = []
                st.rerun()

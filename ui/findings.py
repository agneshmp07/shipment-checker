"""'What we found in your file' pop-up: every booking with problems, in plain English."""
from __future__ import annotations

from typing import Callable

import streamlit as st

from core.check import Evaluation
from core.findings import findings
from core.rules import scorecard
from ui import correct, fixflow

STATUS = {"Blocked": ("red", ":material/block:", "Can't ship yet"),
          "Warnings": ("orange", ":material/warning:", "Can ship — check the warnings"),
          "Ready": ("green", ":material/check_circle:", "Ready to ship")}


def _bullets(lines: list[str]) -> str:
    return "\n".join(f"- {line}" for line in lines)


def _open(booking_id: str):
    st.session_state.focus_booking = booking_id
    st.session_state.focus_toast = True
    st.session_state.pop("batch_table", None)          # clear any row picked in the table


@st.dialog("What we found in your file", width="large", icon=":material/fact_check:")
def findings_dialog(evals: list[Evaluation], fix_all: Callable[[], None]):
    blocked = [e for e in evals if e.status == "Blocked"]
    warned = [e for e in evals if e.status == "Warnings"]
    ready = [e for e in evals if e.status == "Ready"]
    with st.container(horizontal=True):
        st.badge(f"{len(blocked)} can't ship yet", color="red", icon=":material/block:")
        st.badge(f"{len(warned)} with warnings", color="orange", icon=":material/warning:")
        st.badge(f"{len(ready)} ready to ship", color="green", icon=":material/check_circle:")

    if not blocked and not warned:
        st.success("Every booking passes all 10 checks — they're ready to ship.", icon=":material/check_circle:")
        return

    st.write("Here's what needs attention, starting with the bookings that can't ship yet. Press **Fix** on a "
             "booking to correct it — we'll fix what we can, you change the rest, then come straight back here.")
    if st.button("Fix all high-confidence mistakes", type="primary", icon=":material/auto_fix_high:",
                 help="Applies only the fixes we're confident about; the rest stay for you to decide."):
        fix_all()
        st.rerun()

    for ev in blocked + warned:
        b = ev.booking
        colour, icon, words = STATUS[ev.status]
        f = findings(ev)
        with st.container(border=True):
            st.markdown(f"**{b.booking_id} · {b.seller_name or 'Seller not set'}** — "
                        f"{b.origin_city or '?'} → {b.destination_city or '?'}")
            st.badge(words, color=colour, icon=icon)
            score = scorecard(b, ev.issues)
            broke = [r["rule"] for r in score if r["state"] in ("red", "amber")]
            unchecked = [r["rule"] for r in score if r["state"] == "unchecked"]
            st.caption(f"Passed **{sum(r['state'] == 'pass' for r in score)} of 10** rules"
                       + (f" · broke {', '.join(broke)}" if broke else "")
                       + (f" · not checked (data missing): {', '.join(unchecked)}" if unchecked else ""))
            st.markdown(":material/error: **What's wrong**\n" + _bullets(f.wrong))
            if f.recommend:
                st.markdown(":material/lightbulb: **Our recommendation**\n" + _bullets(f.recommend))
            bid = b.booking_id
            autos = correct.suggestions(ev)
            with st.container(horizontal=True, vertical_alignment="center"):
                if st.button(f"Fix {bid}", key=f"find-fix-{bid}", type="primary", icon=":material/build:",
                             help="Opens this booking: apply our fixes or change the fields yourself, then come back."):
                    fixflow.open_fix(bid)
                    st.rerun()
                st.caption(f":material/auto_fix_high: {len(autos)} automatic fix{'es' if len(autos) != 1 else ''} "
                           "ready" if autos else ":material/edit: Needs your input — you'll see exactly what to change")
                if st.button("View details", key=f"find-open-{bid}", type="tertiary", on_click=_open, args=(bid,)):
                    st.rerun()

    if ready:
        st.caption("Ready to ship, nothing to fix: " + ", ".join(e.booking.booking_id or "?" for e in ready))

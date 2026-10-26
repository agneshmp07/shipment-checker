"""'What we found in your file' pop-up: every booking with problems, in plain English."""
from __future__ import annotations

from typing import Callable

import streamlit as st

from core.check import Evaluation
from core.findings import findings
from ui import correct

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

    st.write("Here's what needs attention, starting with the bookings that can't ship yet. For each one you'll "
             "see what's wrong, what to change, and what we recommend.")
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
            st.markdown(":material/error: **What's wrong**\n" + _bullets(f.wrong))
            st.markdown(":material/build: **What to fix** — tick the fixes we can make for you")
            picks = correct.fix_list(ev, f.fix)
            if f.recommend:
                st.markdown(":material/lightbulb: **Our recommendation**\n" + _bullets(f.recommend))
            bid = b.booking_id
            with st.container(horizontal=True):
                if picks:
                    n = sum(bool(st.session_state.get(s["key"])) for s in picks)
                    if st.button(f"Apply ticked fixes ({n})", key=f"find-apply-{bid}", type="primary",
                                 icon=":material/auto_fix_high:", disabled=n == 0):
                        correct.apply_picks(ev, picks)
                        st.session_state.show_findings = True          # reopen with the updated results
                        st.rerun()
                if st.button("Edit by hand", key=f"find-edit-{bid}", icon=":material/edit:",
                             help="Opens this booking with every field and item ready to edit."):
                    _open(bid)
                    st.session_state.manual_open = bid
                    st.rerun()
                if st.button(f"Open {bid}", key=f"find-open-{bid}", icon=":material/open_in_new:",
                             on_click=_open, args=(bid,)):
                    st.rerun()

    if ready:
        st.caption("Ready to ship, nothing to fix: " + ", ".join(e.booking.booking_id or "?" for e in ready))

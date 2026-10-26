"""Check a file: upload Sheets 1 & 2 -> summary + actions -> bookings table -> one booking in tabs.

What's wrong in each booking is explained in the "What we found" pop-up, so the page itself
stays short: three status tiles, one row of actions, a five-column table, and the selected
booking's details organised in tabs.
"""
from collections import Counter
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

from core import fmt
from core.check import evaluate
from core.diagnosis import fix_all
from core.excel_export import corrected_workbook
from core.excel_loader import load_workbook
from core.rules import TITLES
from ui.brand import how_to, page_title
from ui import correct, scan
from ui.findings import findings_dialog
from ui.results import carriers_or_warning, render_evaluation, render_issue

page_title("Check a bookings file", "Upload your Bookings and Items sheets and see every booking checked "
           "against the 10 rules in seconds.")
carriers = carriers_or_warning()

uploaded = st.file_uploader("Bookings file (.xlsx)", type=["xlsx"])

# Load once per file; keep the Booking objects in session state so fixes persist.
if uploaded is not None and st.session_state.get("upload_source") != uploaded.file_id:
    res = load_workbook(uploaded.getvalue())
    st.session_state.update(upload_source=uploaded.file_id, upload_name=uploaded.name,
                            upload_bytes=uploaded.getvalue(), fix_all_result=None, show_findings=True, play_scan=True,
                            focus_booking=None,
                            upload_bookings=res.bookings, upload_file_issues=res.file_issues,
                            upload_notes=res.notes, upload_pristine=[b.model_dump() for b in res.bookings])

bookings = st.session_state.get("upload_bookings")
file_issues = st.session_state.get("upload_file_issues", [])
if bookings is None:
    how_to("upload", [
        ("Upload your file", "Tap Upload and pick your .xlsx file: the Bookings and Items sheets, filled in "
                             "from row 4. There's no submit button — it's checked as soon as it uploads."),
        ("See what's wrong", "A summary opens straight away: what's wrong in each booking, what to fix, and "
                             "what we recommend."),
        ("Fix and download", "Fix mistakes in one tap, download your corrected file, and open any booking for "
                             "its carrier, confirmation and commercial invoice."),
    ])
    st.stop()

if file_issues:
    with st.expander(f"{len(file_issues)} problem(s) with the file itself", icon=":material/error:",
                     expanded=not bookings):
        for n, issue in enumerate(file_issues):
            render_issue(issue, f"file-{n}")
if not bookings:
    st.error("We couldn't find any bookings in this file — see the problems above.", icon=":material/error:")
    st.stop()

today = date.today()
evals = [evaluate(b, carriers, today) for b in bookings]
if st.session_state.pop("play_scan", False):          # once per new file: the checking animation
    st.html(scan.overlay(evals, st.session_state.get("upload_name", "your file")))
    st.html(scan.SKIP_JS, unsafe_allow_javascript=True)


def _fix_all():
    before = {b.booking_id: evaluate(b, carriers, today).status for b in bookings}
    changed = fix_all(bookings, lambda b: evaluate(b, carriers, today))
    st.session_state.fix_all_result = {"changed": changed, "before": before}


def _undo_all():
    res = load_workbook(st.session_state.upload_bytes)
    st.session_state.update(upload_bookings=res.bookings, upload_file_issues=res.file_issues,
                            fix_all_result=None, upload_pristine=[b.model_dump() for b in res.bookings])


# ---- Summary: three tiles + one row of actions --------------------------------------------------
counts = Counter(ev.status for ev in evals)
st.caption(f"Results for **{st.session_state.upload_name}** · {len(evals)} booking{'s' if len(evals) != 1 else ''}")
with st.container(horizontal=True):
    st.metric(":material/block: Can't ship yet", counts["Blocked"], border=True)
    st.metric(":material/warning: Warnings", counts["Warnings"], border=True)
    st.metric(":material/check_circle: Ready to ship", counts["Ready"], border=True)

original = st.session_state.get("upload_bytes")
pristine = st.session_state.get("upload_pristine")
changes = bool(original) and (pristine is None or [b.model_dump() for b in bookings] != pristine)
problems = counts["Blocked"] + counts["Warnings"]
with st.container(horizontal=True):
    if st.button(f"See what's wrong ({problems})" if problems else "See the summary", type="primary",
                 icon=":material/report:", help="What's wrong in each booking, what to fix, and our recommendation."):
        st.session_state.show_findings = True
    st.download_button("Download corrected file", lambda: corrected_workbook(original, bookings)[0],
                       file_name=f"{Path(st.session_state.upload_name).stem}_corrected.xlsx",
                       icon=":material/download:", disabled=not changes,
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                       help="Your file with every fix applied, changed cells highlighted in yellow, and a "
                            "'Oops-Proof changes' sheet listing what changed.")
if st.session_state.pop("show_findings", False):
    findings_dialog(evals, _fix_all)

# One quiet line: most common problem, what Fix all did, and undo
notes = []
rule_counts = Counter(r for ev in evals for r in {i.rule_id for i in ev.issues} if r != "DATA")
if rule_counts:
    (top_rule, top_n), = rule_counts.most_common(1)
    notes.append(f"Most common problem: {TITLES[top_rule]} ({top_n} of {len(evals)})")
result = st.session_state.get("fix_all_result")
if result is not None:
    changed = result["changed"]
    n_fixed = sum(len(v) for v in changed.values())
    notes.append(f"Corrected {n_fixed} mistake{'s' if n_fixed != 1 else ''} so far" if changed
                 else "Nothing was changed — the rest need your decision")
with st.container(horizontal=True, vertical_alignment="center"):
    if notes:
        st.caption(" · ".join(notes))
    if changes:
        st.button("Undo all fixes", icon=":material/undo:", on_click=_undo_all, type="tertiary")
correct.render(evals, bookings)

if result is not None and result["changed"]:
    now = {e.booking.booking_id: e.status for e in evals}
    with st.expander("See what was corrected", icon=":material/auto_fix_high:"):
        for bid, items in result["changed"].items():
            st.markdown(f"**{bid}** ({result['before'][bid].lower()} → {now.get(bid, '?').lower()}): "
                        + "; ".join(items))

# ---- Bookings table ------------------------------------------------------------------------------
table = pd.DataFrame([{
    "Booking": ev.booking.booking_id, "Status": ev.badge,
    "Route": f"{ev.booking.origin_city} → {ev.booking.destination_city}",
    "Seller": ev.booking.seller_name,
    "Best carrier": (f"{ev.recommendation.winner.option.carrier} · {fmt.money(ev.recommendation.winner.total_cost)}"
                     if ev.recommendation.winner else "—"),
} for ev in evals])
st.caption("Tap a row to open that booking.")
event = st.dataframe(table, hide_index=True, on_select="rerun", selection_mode="single-row",
                     key="batch_table")
rows = event.selection.rows
ids = [e.booking.booking_id for e in evals]
focus = st.session_state.get("focus_booking")
if rows:
    selected = rows[0]
    st.session_state.focus_booking = None
elif focus in ids:
    selected = ids.index(focus)
    if st.session_state.pop("focus_toast", False):
        st.toast(f"Showing {focus} — scroll down to its details.", icon=":material/arrow_downward:")
else:
    selected = 0

st.divider()
render_evaluation(evals[selected], key=f"upload-{selected}")

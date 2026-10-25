"""Upload page: Sheets 1 & 2 -> batch dashboard -> per-booking results."""
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
from ui.findings import findings_dialog
from ui.results import carriers_or_warning, render_evaluation, render_issue

page_title("Check a bookings file", "Upload your Bookings and Items sheets and see every booking checked "
           "against the 10 rules in seconds.")
how_to("upload", [
    ("Upload your file", "Tap Upload and pick your .xlsx file: the Bookings and Items sheets, filled in from "
                         "row 4. There's no submit button — it's checked as soon as it uploads."),
    ("Read the dashboard", "See how many bookings are ready, need warnings checked, or are blocked, and "
                           "the most common mistake."),
    ("Open a booking and fix it", "Tap a row. Each problem shows the real numbers, why it matters and a "
                                  "one-tap fix; the status updates instantly."),
])
carriers = carriers_or_warning()

uploaded = st.file_uploader("Bookings file (.xlsx)", type=["xlsx"])

# Load once per file; keep the Booking objects in session state so fixes persist.
if uploaded is not None and st.session_state.get("upload_source") != uploaded.file_id:
    res = load_workbook(uploaded.getvalue())
    st.session_state.update(upload_source=uploaded.file_id, upload_name=uploaded.name,
                            upload_bytes=uploaded.getvalue(), fix_all_result=None, show_findings=True,
                            focus_booking=None,
                            upload_bookings=res.bookings, upload_file_issues=res.file_issues,
                            upload_notes=res.notes)

bookings = st.session_state.get("upload_bookings")
file_issues = st.session_state.get("upload_file_issues", [])
if bookings is None:
    st.stop()

# No submit button is needed: say clearly that the file has been checked and where the results are.
if bookings:
    n = len(bookings)
    st.success(f"Checked {n} booking{'s' if n != 1 else ''} from {st.session_state.upload_name} — "
               "[jump to the results ↓](#results)", icon=":material/task_alt:")
else:
    st.error("We couldn't find any bookings in this file. The problems are listed below.",
             icon=":material/error:")

st.divider()
st.subheader(f"Results — {st.session_state.upload_name}", anchor="results")
if file_issues:
    with st.expander(f"{len(file_issues)} problem(s) with the file itself", icon=":material/error:",
                     expanded=not bookings):
        for n, issue in enumerate(file_issues):
            render_issue(issue, f"file-{n}")
if not bookings:
    st.stop()

today = date.today()
evals = [evaluate(b, carriers, today) for b in bookings]

# ---- Batch dashboard -------------------------------------------------------
counts = Counter(ev.status for ev in evals)
rule_counts = Counter(r for ev in evals for r in {i.rule_id for i in ev.issues})
with st.container(horizontal=True):
    st.metric("Bookings", len(evals), border=True)
    st.metric("🟢 Ready to ship", counts["Ready"], border=True)
    st.metric("🟠 Ready with warnings", counts["Warnings"], border=True)
    st.metric("🔴 Blocked", counts["Blocked"], border=True)
if rule_counts:
    (top_rule, top_n), = rule_counts.most_common(1)
    name = "Problems in the input data" if top_rule == "DATA" else f"{top_rule} · {TITLES[top_rule]}"
    st.markdown(f"**Most common problem:** {name} — in {top_n} of {len(evals)} bookings.")

# ---- Fix all + corrected file ---------------------------------------------------------------
def _fix_all():
    before = {b.booking_id: evaluate(b, carriers, today).status for b in bookings}
    changed = fix_all(bookings, lambda b: evaluate(b, carriers, today))
    st.session_state.fix_all_result = {"changed": changed, "before": before}


def _undo_all():
    res = load_workbook(st.session_state.upload_bytes)
    st.session_state.update(upload_bookings=res.bookings, upload_file_issues=res.file_issues,
                            fix_all_result=None)


original = st.session_state.get("upload_bytes")
corrected, changes = corrected_workbook(original, bookings) if original else (b"", [])
problems = sum(e.status != "Ready" for e in evals)
with st.container(horizontal=True):
    if st.button(f"See what's wrong ({problems})" if problems else "See the summary", type="primary",
                 icon=":material/report:", help="What's wrong in each booking, what to fix, and our recommendation."):
        st.session_state.show_findings = True
    st.button("Fix all high-confidence mistakes", icon=":material/auto_fix_high:",
              on_click=_fix_all, help="Applies only the fixes ShipCheck is highly confident about. Guesses and "
              "things only you can decide (an HS code, booking a delivery slot) are left for you.")
    stem = Path(st.session_state.upload_name).stem
    st.download_button("Download corrected file", corrected or b"", file_name=f"{stem}_corrected.xlsx",
                       icon=":material/download:", disabled=not changes,
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                       help="Your file with every fix applied, changed cells highlighted in yellow, and a "
                            "'ShipCheck changes' sheet listing what changed.")
    if changes:
        st.button("Undo all fixes", icon=":material/undo:", on_click=_undo_all)
if st.session_state.pop("show_findings", False):
    findings_dialog(evals, _fix_all)
result = st.session_state.get("fix_all_result")
if result is not None:
    changed = result["changed"]
    now = {e.booking.booking_id: e.status for e in evals}
    if changed:
        n = sum(len(v) for v in changed.values())
        cleared = sum(now.get(bid) == "Ready" and result["before"].get(bid) != "Ready" for bid in changed)
        st.success(f"Fixed {n} mistake{'s' if n != 1 else ''} in {len(changed)} booking"
                   f"{'s' if len(changed) != 1 else ''} — {cleared} now ready to ship.", icon=":material/auto_fix_high:")
        with st.expander("See what changed"):
            for bid, items in changed.items():
                st.markdown(f"**{bid}** ({result['before'][bid].lower()} → {now.get(bid, '?').lower()}): "
                            + "; ".join(items))
    left = sum(e.status != "Ready" for e in evals)
    if left:
        st.info(f"{left} booking{'s' if left != 1 else ''} still need{'s' if left == 1 else ''} your decision — "
                "open each one below to see why and fix it.", icon=":material/person_check:")
    elif not changed:
        st.info("Nothing needed fixing.", icon=":material/check_circle:")

table = pd.DataFrame([{
    "Booking": ev.booking.booking_id, "Seller": ev.booking.seller_name,
    "Route": f"{ev.booking.origin_city} → {ev.booking.destination_city}",
    "Status": ev.badge,
    "Red": sum(i.severity == "Red" for i in ev.issues),
    "Amber": sum(i.severity == "Amber" for i in ev.issues),
    "Rules broken": ", ".join(sorted({"Input" if i.rule_id == "DATA" else i.rule_id for i in ev.issues})) or "—",
    "Carrier": ev.recommendation.winner.option.carrier if ev.recommendation.winner else "—",
    "Cost": fmt.money(ev.recommendation.winner.total_cost) if ev.recommendation.winner else "—",
} for ev in evals])
st.caption("Click a row to see that booking's details.")
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

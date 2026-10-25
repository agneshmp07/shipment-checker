"""Upload page: Sheets 1 & 2 -> batch dashboard -> per-booking results."""
from collections import Counter
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

from core import fmt
from core.check import evaluate
from core.excel_loader import load_workbook
from core.rules import TITLES
from ui.results import carriers_or_warning, render_evaluation, render_issue

SAMPLE = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "planted_mistakes.xlsx"

st.title("Check a bookings file")
st.write("Upload an Excel file with the **Bookings** sheet (one row per shipment) and the **Items** "
         "sheet (one row per product). Every booking is checked against the 10-rule rulebook.")
carriers = carriers_or_warning()

uploaded = st.file_uploader("Bookings file (.xlsx)", type=["xlsx"])
with st.container(horizontal=True):
    use_sample = st.button("Try the sample file", icon=":material/science:",
                           help="14 bookings with planted mistakes, including 3 clean ones")
    if SAMPLE.exists():
        st.download_button("Download the sample file", SAMPLE.read_bytes(), file_name="sample_bookings.xlsx",
                           icon=":material/download:")

# Load once per file; keep the Booking objects in session state so fixes persist.
if uploaded is not None and st.session_state.get("upload_source") != uploaded.file_id:
    res = load_workbook(uploaded.getvalue())
    st.session_state.update(upload_source=uploaded.file_id, upload_name=uploaded.name,
                            upload_bookings=res.bookings, upload_file_issues=res.file_issues,
                            upload_notes=res.notes)
elif use_sample:
    res = load_workbook(SAMPLE)
    st.session_state.update(upload_source="sample", upload_name="Sample file (planted mistakes)",
                            upload_bookings=res.bookings, upload_file_issues=res.file_issues,
                            upload_notes=res.notes)

bookings = st.session_state.get("upload_bookings")
file_issues = st.session_state.get("upload_file_issues", [])
if bookings is None:
    st.stop()

st.divider()
st.subheader(f"Results — {st.session_state.upload_name}")
if file_issues:
    with st.expander(f"{len(file_issues)} problem(s) with the file itself", icon=":material/error:",
                     expanded=not bookings):
        for n, issue in enumerate(file_issues):
            render_issue(issue, f"file-{n}")
for note in st.session_state.get("upload_notes", []):
    st.caption(f":material/info: {note}")
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
selected = rows[0] if rows else 0

st.divider()
render_evaluation(evals[selected], key=f"upload-{selected}")

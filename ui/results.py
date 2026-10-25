"""Results screen shared by the chat and upload pages: one booking's Evaluation."""
from __future__ import annotations

from datetime import date
from typing import Callable, Optional

import pandas as pd
import streamlit as st

from core import fmt, llm
from core.carriers import label, load_carriers
from core.check import Evaluation, evaluate
from core.diagnosis import apply_fix, diagnose
from core.confirmation import DELIVERY_ASSUMPTION
from core.report import html_report
from core.rules import RULE_NAMES
from core.trade_connect import load_directory, match_buyers
from ui.brand import carrier_cards, status_banner
from ui.invoice import render_invoice

STATUS_STYLE = {  # status -> (badge colour, icon)
    "Blocked": ("red", ":material/block:"),
    "Warnings": ("orange", ":material/warning:"),
    "Ready": ("green", ":material/check_circle:"),
}
SEVERITY_COLOUR = {"Red": "red", "Amber": "orange"}
CONFIDENCE_COLOUR = {"High": "green", "Medium": "blue", "Low": "gray"}
STEP_ICON = {"todo": ":material/radio_button_unchecked:", "warn": ":material/warning:",
             "done": ":material/check_circle:"}


@st.cache_data(ttl=600)
def get_carriers():
    return load_carriers()


def carriers_or_warning():
    carriers = get_carriers()
    if not carriers:
        st.warning("The carrier rate card (data/carriers.json) is missing, so no carrier can be "
                   "recommended and the pallet-weight check (R-05) can't run.", icon=":material/error:")
    return carriers


@st.cache_data(ttl=3600, max_entries=500, show_spinner=False)
def dg_hints(items: tuple[tuple[str, str], ...]) -> list[dict]:
    return [h.model_dump() for h in llm.llm_dg_second_opinion(list(items))]


def status_badge(ev: Evaluation):
    colour, icon = STATUS_STYLE[ev.status]
    st.badge(ev.badge[2:], color=colour, icon=icon)    # badge text without the emoji


def _do_fix(ev: Evaluation, action: dict, key: str, on_fix: Optional[Callable[[str], None]]):
    """Button callback: change the booking, re-run every check, remember before -> after."""
    change = apply_fix(ev.booking, action)
    after = evaluate(ev.booking, get_carriers(), date.today())
    msg = (f"Applied: {change} · status {ev.badge} → {after.badge} · "
           f"issues {len(ev.issues)} → {len(after.issues)}")
    st.session_state[f"fixmsg-{key}"] = msg
    if on_fix:
        on_fix(msg)


def fix_button(ev, action, label, btn_key, msg_key, on_fix):
    if action:
        st.button(label, key=btn_key, icon=":material/build:", on_click=_do_fix,
                  args=(ev, action, msg_key, on_fix))


def render_issue(issue, key: str, ev: Optional[Evaluation] = None, on_fix=None, msg_key: str = ""):
    with st.container(border=True):
        rule = "Input" if issue.rule_id == "DATA" else issue.rule_id
        st.markdown(f":{SEVERITY_COLOUR[issue.severity]}-badge[{issue.severity}] "
                    f"**{rule} · {issue.title}**")
        st.write(issue.explanation)
        st.markdown(f"**Why it matters:** {issue.why_it_matters}")
        st.markdown(f"**How to fix:** {issue.fix}")
        if ev is not None and issue.fix_action:
            fix_button(ev, issue.fix_action, issue.fix_action.get("label", "Apply fix"), f"{key}-btn",
                       msg_key, on_fix)


def render_evaluation(ev: Evaluation, key: str, on_fix: Optional[Callable[[str], None]] = None):
    """Full results for one booking. `key` keeps widget keys unique per booking.
    on_fix(message) is called after an Apply-fix button changes the booking."""
    b, rec = ev.booking, ev.recommendation
    # "Ask AI" talks about the booking on screen (remembered per page)
    st.session_state.assistant_focus = (st.session_state.get("current_page"), ev)

    # Header
    with st.container(border=True):
        status_banner(ev)
        with st.container(horizontal=True):
            st.metric("Pallets", fmt.num(b.pallets), border=True)
            st.metric("Cartons", fmt.num(b.cartons), border=True)
            st.metric("Declared value", fmt.money(b.total_declared_value), border=True)
            st.metric("Gross weight", fmt.kg(b.total_gross_weight_kg), border=True)
            st.metric("Weight per pallet", fmt.kg(rec.weight_per_pallet), border=True)
        with st.expander(f"Items ({len(b.items)})"):
            st.dataframe(pd.DataFrame([{
                "SKU": it.sku, "Description": it.description, "HS code": it.hs_code,
                "Quantity": it.quantity, "Unit price (£)": it.unit_price,
                "Units/carton": it.units_per_carton, "Cartons": it.cartons,
                "Unit weight (kg)": it.unit_weight_kg, "Country of origin": it.country_of_origin,
            } for it in b.items]), hide_index=True)

    # Checks
    st.markdown("#### :material/fact_check: Checks")
    failed = {i.rule_id for i in ev.issues}
    passed = [r for r in RULE_NAMES if r not in failed]
    msg = st.session_state.pop(f"fixmsg-{key}", None)
    if msg:
        st.success(msg, icon=":material/build:")
    if not ev.issues:
        st.success("All 10 rulebook checks pass.", icon=":material/check_circle:")
    roots, remaining = diagnose(b, ev.issues)
    by_key = {f"{i.rule_id}:{i.item_sku or ''}": i for i in ev.issues}
    for n, rc in enumerate(roots):
        with st.container(border=True):
            n_fix = len(rc.fixes)
            head = f"1 root problem → fixes {n_fix} issues" if n_fix > 1 else "Likely cause"
            st.markdown(f":violet-badge[{head}] :{CONFIDENCE_COLOUR[rc.confidence]}-badge[{rc.confidence} "
                        f"confidence] **{rc.title}**")
            st.write(rc.explanation)
            explained = [by_key[k] for k in rc.fixes if k in by_key]
            st.caption("Explains: " + " · ".join(i.title for i in explained))
            with st.expander("Show the details of these issues"):
                for m, issue in enumerate(explained):
                    render_issue(issue, f"{key}-root{n}-{m}")
            fix_button(ev, rc.fix_action, rc.fix_label, f"{key}-root-{n}-btn", key, on_fix)
    if roots and remaining:
        st.markdown("**Other issues**")
    for n, issue in enumerate(remaining):
        render_issue(issue, f"{key}-issue-{n}", ev, on_fix, msg_key=key)
    if llm.available():
        flagged = {i.item_sku for i in ev.issues if i.rule_id == "R-06"}
        unflagged = tuple((it.sku, it.description) for it in b.items
                          if it.sku and it.description and it.sku not in flagged)
        for h in dg_hints(unflagged):
            st.warning(f"**Possible dangerous goods — please confirm:** {h['sku']} — {h['reason']}. "
                       "This is an AI suggestion only; it does not change the status.",
                       icon=":material/help:")
    if ev.issues and passed:
        with st.expander(f"See the {len(passed)} checks that passed", icon=":material/check_circle:"):
            st.markdown(" · ".join(f"✅ {RULE_NAMES[r]}" for r in passed))

    # Carrier
    st.markdown("#### :material/local_shipping: Recommended carrier")
    if rec.winner:
        carrier_cards(rec)
        st.write(rec.reason)
        if rec.trade_off:
            st.caption(f"Trade-off: {rec.trade_off}")
    else:
        st.error(rec.reason, icon=":material/local_shipping:")
    if rec.all_options:
        with st.expander("Compare all carriers on this route"):
            st.dataframe(pd.DataFrame([{
                "Status": r.status, "Carrier": label(r.option), "Total cost (£)": r.total_cost,
                "Transit (days)": r.option.transit_days, "On time (%)": r.option.on_time_rate,
                "Max per pallet (kg)": r.option.max_weight_per_pallet_kg, "Notes": r.reason,
            } for r in rec.all_options]), hide_index=True,
                column_config={"Total cost (£)": st.column_config.NumberColumn(format="£%.2f")})

    # Confirmation + next steps
    st.markdown("#### :material/assignment_turned_in: Confirmation")
    (st.info if ev.status == "Blocked" else st.success)(ev.summary)
    st.caption("Delivery date is an estimate.", help=DELIVERY_ASSUMPTION)

    st.markdown("#### :material/timeline: What happens next")
    for n, s in enumerate(ev.next_steps, 1):
        st.markdown(f"{STEP_ICON[s['state']]} **{n}. {s['step']}** — {s['detail']}")

    matches = match_buyers(b, load_directory())[:2]
    if matches:
        st.markdown("#### :material/storefront: Buyers for these goods")
        for m in matches:
            st.markdown(f"**{m.business.name}** — {' · '.join(m.reasons)}")
        try:
            st.page_link("app_pages/trade_connect.py", label="See all matches and message buyers in the Marketplace",
                         icon=":material/arrow_forward:")
        except Exception:      # rendered outside the multipage app (e.g. a test harness)
            st.caption("See all matches and message buyers in the Marketplace.")

    render_invoice(ev, key)

    st.download_button("Download booking report (HTML)", html_report(ev),
                       file_name=f"booking_{b.booking_id or 'new'}.html", mime="text/html",
                       icon=":material/download:", key=f"{key}-download")

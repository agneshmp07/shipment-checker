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
from core.dangerous_goods import possible_battery
from core.labels import MAX_LABELS, label_count, labels_pdf
from core.report import html_report
from core.rules import scorecard
from core.trade_connect import load_directory, match_buyers
from ui.brand import carrier_cards, rule_chips, status_banner
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


def render_evaluation(ev: Evaluation, key: str, on_fix: Optional[Callable[[str], None]] = None,
                      editable: bool = False):
    """Full results for one booking. `key` keeps widget keys unique per booking.
    on_fix(message) is called after an Apply-fix button changes the booking."""
    b, rec = ev.booking, ev.recommendation
    # "Ask AI" talks about the booking on screen (remembered per page)
    st.session_state.assistant_focus = (st.session_state.get("current_page"), ev)

    # Header: status in plain words and the four numbers people check first
    status_banner(ev)
    with st.container(horizontal=True):
        st.metric("Pallets", fmt.num(b.pallets), border=True)
        st.metric("Cartons", fmt.num(b.cartons), border=True)
        st.metric("Declared value", fmt.money(b.total_declared_value), border=True)
        st.metric("Weight per pallet", fmt.kg(rec.weight_per_pallet), border=True)
    with st.expander(f"Items ({len(b.items)}) · gross weight {fmt.kg(b.total_gross_weight_kg)}",
                     icon=":material/inventory_2:"):
        st.dataframe(pd.DataFrame([{
            "SKU": it.sku, "Description": it.description, "HS code": it.hs_code,
            "Quantity": it.quantity, "Unit price (£)": it.unit_price,
            "Units/carton": it.units_per_carton, "Cartons": it.cartons,
            "Unit weight (kg)": it.unit_weight_kg, "Country of origin": it.country_of_origin,
        } for it in b.items]), hide_index=True)

    t_problems, t_carrier, t_confirm, t_invoice, t_buyers = st.tabs(
        [":material/rule: 10-rule check", ":material/local_shipping: Carrier",
         ":material/assignment_turned_in: Confirmation", ":material/receipt_long: Invoice",
         ":material/storefront: Buyers"], key=f"{key}-tabs", on_change="rerun")

    # ---- 10-rule check: what passed, what broke, and the fixes ----
    with t_problems:
        st.html(rule_chips(scorecard(b, ev.issues)))      # R-01 … R-10: passed, broken or not checked
        if editable and ev.issues:                      # upload page: the same fix window as the pop-up
            if st.button(f"Fix {b.booking_id}", key=f"{key}-fix", type="primary", icon=":material/build:",
                         help="Apply our fixes or change the fields yourself, in one window."):
                st.session_state.fix_target = b.booking_id
                st.rerun()
        msg = st.session_state.pop(f"fixmsg-{key}", None)
        if msg:
            st.success(msg, icon=":material/build:")
        if not ev.issues:
            st.success("All 10 checks pass — nothing to fix.", icon=":material/check_circle:")
        roots, remaining = diagnose(b, ev.issues)
        by_key = {f"{i.rule_id}:{i.item_sku or ''}": i for i in ev.issues}
        for n, rc in enumerate(roots):
            with st.container(border=True):
                n_fix = len(rc.fixes)
                sure = rc.confidence == "High"
                head = (f"1 root problem → fixes {n_fix} issues" if n_fix > 1 else "Root cause") if sure                     else "Possible cause — not certain"
                st.markdown(f":violet-badge[{head}] :{CONFIDENCE_COLOUR[rc.confidence]}-badge[{rc.confidence} "
                            f"confidence] **{rc.title}**")
                st.write(rc.explanation)
                explained = [by_key[k] for k in rc.fixes if k in by_key]
                with st.expander("Explains: " + " · ".join(i.title for i in explained)):
                    for m, issue in enumerate(explained):
                        render_issue(issue, f"{key}-root{n}-{m}")
                if sure:                                # only certain fixes get a button
                    fix_button(ev, rc.fix_action, rc.fix_label, f"{key}-root-{n}-btn", key, on_fix)
                else:
                    st.caption(":material/front_hand: We're not sure enough to change this for you — "
                               "check it and enter the right value yourself.")
        for n, issue in enumerate(remaining):
            render_issue(issue, f"{key}-issue-{n}", ev, on_fix, msg_key=key)
        flagged_dg = {i.item_sku for i in ev.issues if i.rule_id == "R-06"}
        for it in b.items:
            word = possible_battery(it.description) if it.sku not in flagged_dg else None
            if word:
                st.warning(f"**Please confirm — possible built-in lithium battery:** {it.sku} "
                           f"({it.description}) looks like a battery-powered product (“{word}”). If it has a "
                           "lithium battery, it needs the carrier's dangerous-goods paperwork. This doesn't "
                           "change the status.", icon=":material/battery_alert:")
        if llm.available():
            flagged = {i.item_sku for i in ev.issues if i.rule_id == "R-06"}
            unflagged = tuple((it.sku, it.description) for it in b.items
                              if it.sku and it.description and it.sku not in flagged)
            for h in dg_hints(unflagged):
                st.warning(f"**Possible dangerous goods — please confirm:** {h['sku']} — {h['reason']}. "
                           "This is an AI suggestion only; it does not change the status.",
                           icon=":material/help:")

    # ---- Carrier ----
    with t_carrier:
        if rec.winner:
            st.markdown(f"**{rec.headline}**")
            carrier_cards(rec)
            st.write(rec.reason)
            if rec.trade_off:
                st.caption(f"Trade-off: {rec.trade_off}")
        else:
            st.error(rec.reason, icon=":material/local_shipping:")
            if rec.all_options:
                carrier_cards(rec)
        if rec.all_options:
            with st.expander("All the numbers, and how “Balanced” is scored"):
                st.caption("Balanced scores each carrier 0–1 on cost (lower is better), speed (fewer days is "
                           "better) and on-time rate (higher is better), then weights them 40% · 30% · 30%.")
                st.dataframe(pd.DataFrame([{
                    "Status": r.status, "Carrier": label(r.option), "Total cost (£)": r.total_cost,
                    "Transit (days)": r.option.transit_days, "On time (%)": r.option.on_time_rate,
                    "Max per pallet (kg)": r.option.max_weight_per_pallet_kg, "Notes": r.reason,
                } for r in rec.all_options]), hide_index=True,
                    column_config={"Total cost (£)": st.column_config.NumberColumn(format="£%.2f")})

    # ---- Confirmation & next steps ----
    with t_confirm:
        (st.info if ev.status == "Blocked" else st.success)(ev.summary)
        st.caption("Delivery date is an estimate.", help=DELIVERY_ASSUMPTION)
        st.markdown("**What happens next**")
        for n, s in enumerate(ev.next_steps, 1):
            st.markdown(f"{STEP_ICON[s['state']]} **{n}. {s['step']}** — {s['detail']}")
        if any(i.rule_id in ("R-03", "R-04") for i in ev.issues):
            st.caption(":material/warning: Fix the carton counts first, so the labels match what you declared.")
        inv = st.session_state.get(f"invoice-details-{b.booking_id}")
        consignee = None
        if inv is not None:
            consignee = (inv.buyer_name if inv.consignee_same_as_buyer else inv.consignee_name) or None
        too_many = label_count(b) > MAX_LABELS
        with st.container(horizontal=True):
            st.download_button("Carton labels (PDF)", lambda: labels_pdf(b, consignee),   # built on click
                               file_name=f"labels_{b.booking_id or 'new'}.pdf", mime="application/pdf",
                               icon=":material/label:", key=f"{key}-labels", type="primary", disabled=too_many,
                               help=(f"{label_count(b):,} cartons is more than the {MAX_LABELS:,} labels we print "
                                     "at once — check the carton counts." if too_many else
                                     "One label per carton — “Carton 1 of 90” — with product, units, "
                                     "from / to and a barcode. 8 labels per A4 sheet."))
            st.download_button("Booking report", lambda: html_report(ev),
                               file_name=f"booking_{b.booking_id or 'new'}.html", mime="text/html",
                               icon=":material/download:", key=f"{key}-download")

    # ---- Invoice ----
    with t_invoice:
        render_invoice(ev, key)

    # ---- Buyers ----
    with t_buyers:
        matches = match_buyers(b, load_directory())[:3]
        if not matches:
            st.info("No buyers in the marketplace want these goods yet.", icon=":material/storefront:")
        for m in matches:
            with st.container(border=True):
                st.markdown(f"**{m.business.name}** · {m.business.city}, {m.business.country}")
                st.caption(" · ".join(m.reasons))
        if matches:
            try:
                st.page_link("app_pages/trade_connect.py", label="Message these buyers in the Marketplace",
                             icon=":material/arrow_forward:")
            except Exception:      # rendered outside the multipage app (e.g. a test harness)
                st.caption("Message these buyers in the Marketplace.")

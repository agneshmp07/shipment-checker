"""The pre-flight gate: one clear pass/fail checkpoint before a booking can be confirmed.

All 10 rules run; the booking is CLEARED only when no Red rule is broken and every rule could actually be
checked (a rule skipped for missing data is never treated as a pass). Until then the confirmation, carton
labels and commercial invoice stay locked. Amber warnings don't block, but are listed.
"""
from __future__ import annotations

from html import escape

import streamlit as st

from core.check import Evaluation
from core.rules import scorecard

DOCS = "Confirmation · Carton labels · Commercial invoice"


def gate(ev: Evaluation) -> tuple[bool, list[str]]:
    """(cleared, reasons it isn't) for this booking."""
    score = scorecard(ev.booking, ev.issues)
    reasons = [f"{r['rule']} {r['name']} — broken" for r in score if r["state"] == "red"]
    reasons += [f"{r['rule']} {r['name']} — couldn't be checked (data missing)" for r in score
                if r["state"] == "unchecked"]
    if any(i.rule_id == "DATA" for i in ev.issues):
        reasons.insert(0, "Some required booking details are missing")
    return not reasons, reasons


_CSS = """<style>
.pf{border-radius:18px;padding:16px 18px;margin:4px 0 6px;position:relative;overflow:hidden;
  background:linear-gradient(135deg,rgba(255,90,95,.14),#10213A 60%);border:1px solid rgba(255,90,95,.5);
  animation:scFadeUp .6s cubic-bezier(.22,1,.36,1) both}
.pf.ok{background:linear-gradient(135deg,rgba(46,204,113,.16),#10213A 60%);border-color:rgba(46,204,113,.55)}
.pf-top{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}
.pf-kick{font-size:.68rem;font-weight:800;letter-spacing:.1em;text-transform:uppercase;color:#9FB0C6}
.pf-ttl{font-family:'Plus Jakarta Sans',Inter,sans-serif;font-weight:800;font-size:1.25rem;color:#fff;margin-top:2px}
.pf-stamp{font-family:'Plus Jakarta Sans',Inter,sans-serif;font-weight:900;font-size:.9rem;letter-spacing:.12em;
  padding:6px 14px;border-radius:10px;border:2px solid #FF5A5F;color:#FF8A8D;transform:rotate(-3deg);
  animation:pfStamp .5s cubic-bezier(.34,1.56,.64,1) 1.1s both}
.pf.ok .pf-stamp{border-color:#2ECC71;color:#5BD98C}
.pf-lights{display:grid;grid-template-columns:repeat(10,1fr);gap:6px;margin:14px 0 10px}
.pf-l{border-radius:8px;padding:6px 0;text-align:center;font-size:.68rem;font-weight:800;color:#0E1B2E;
  animation:pfOn .35s ease both;animation-delay:calc(var(--i) * 80ms)}
.pf-l.pass{background:#2ECC71}.pf-l.red{background:#FF5A5F}.pf-l.amber{background:#FF9F43}
.pf-l.unchecked{background:#2A4060;color:#9FB0C6}
.pf-docs{display:flex;align-items:center;gap:8px;font-size:.84rem;color:#D5DEEA}
.pf-docs b{color:#fff}
.pf-why{margin:8px 0 0;padding-left:18px;font-size:.82rem;color:#FFB3B5}
.pf-why li{margin:2px 0}
@keyframes pfOn{from{opacity:.15;transform:scale(.8)}to{opacity:1;transform:none}}
@keyframes pfStamp{from{opacity:0;transform:rotate(-3deg) scale(1.8)}to{opacity:1;transform:rotate(-3deg)}}
@media (max-width:640px){.pf-lights{grid-template-columns:repeat(5,1fr)}.pf-ttl{font-size:1.05rem}}
@media (prefers-reduced-motion:reduce){.pf,.pf-l,.pf-stamp{animation:none}}
</style>"""


def checkpoint(ev: Evaluation):
    """The visible pre-flight panel: 10 rule lights, CLEARED / NOT CLEARED, and what's locked."""
    ok, reasons = gate(ev)
    score = scorecard(ev.booking, ev.issues)
    lights = "".join(f'<div class="pf-l {r["state"]}" style="--i:{n}" title="{escape(r["rule"] + " " + r["name"])}">'
                     f'{r["rule"]}</div>' for n, r in enumerate(score))
    warn = sum(r["state"] == "amber" for r in score)
    if ok:
        title = "Pre-flight cleared" + (f" — {warn} warning{'s' if warn != 1 else ''} to review" if warn else "")
        docs = f"🔓 <span><b>Unlocked:</b> {DOCS}</span>"
        why = ""
    else:
        title = "Pre-flight not cleared — this booking can't be confirmed yet"
        docs = f"🔒 <span><b>Locked until it clears:</b> {DOCS}</span>"
        why = '<ul class="pf-why">' + "".join(f"<li>{escape(r)}</li>" for r in reasons) + "</ul>"
    st.html(f'{_CSS}<div class="pf {"ok" if ok else ""}"><div class="pf-top"><div>'
            f'<div class="pf-kick">Pre-flight check · 10 rules</div><div class="pf-ttl">{escape(title)}</div></div>'
            f'<div class="pf-stamp">{"CLEARED" if ok else "NOT CLEARED"}</div></div>'
            f'<div class="pf-lights">{lights}</div><div class="pf-docs">{docs}</div>{why}</div>')
    return ok


def locked_note(what: str, ev: Evaluation):
    """Shown in place of a locked document."""
    _, reasons = gate(ev)
    st.error(f"**{what} is locked — pre-flight not cleared.** Fix these first:\n"
             + "\n".join(f"- {r}" for r in reasons), icon=":material/lock:")

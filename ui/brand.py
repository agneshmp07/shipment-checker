"""ShipCheck look and feel: hero banner, step cards and the per-page "How to use" guide.

Custom HTML is used only where Streamlit has no native element (the hero banner and
the numbered step cards). Class names are prefixed "sc-" so the CSS can't leak.
"""
from __future__ import annotations

import base64
from pathlib import Path

import streamlit as st

_CSS = """
<style>
.sc-hero{display:flex;flex-wrap:wrap;align-items:flex-end;gap:18px 28px;overflow:hidden;border-radius:22px;padding:34px 34px 30px;
  background:radial-gradient(1200px 400px at 85% -10%,rgba(242,105,15,.35),transparent 60%),
             linear-gradient(135deg,#0F2747 0%,#0A1628 70%);border:1px solid #22406A}
.sc-hero h1{font-family:'Plus Jakarta Sans',Inter,sans-serif;font-weight:800;font-size:2.35rem;
  line-height:1.12;margin:6px 0 10px;color:#fff;max-width:560px}
.sc-hero h1 span{color:#FF8A3D}
.sc-hero p{color:#B9C8DC;font-size:1.05rem;max-width:520px;margin:0 0 16px}
.sc-kicker{display:inline-block;font-size:.78rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;
  color:#FF9A4D;background:rgba(242,105,15,.12);border:1px solid rgba(242,105,15,.35);padding:4px 10px;border-radius:99px}
.sc-chips{display:flex;flex-wrap:wrap;gap:8px}
.sc-chip{font-size:.85rem;color:#EAF0F7;background:rgba(255,255,255,.06);border:1px solid #22406A;
  padding:6px 12px;border-radius:99px}
.sc-hero-text{flex:1 1 380px;min-width:0}
.sc-truck{flex:0 1 300px;width:300px;max-width:100%}
@media (max-width:760px){.sc-hero{padding:24px 20px}.sc-hero h1{font-size:1.8rem}}
.sc-steps{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:14px;margin:4px 0}
.sc-step{background:#12243D;border:1px solid #22406A;border-radius:16px;padding:16px 16px 14px}
.sc-step b{display:flex;align-items:center;gap:10px;font-size:1.02rem;color:#fff;margin-bottom:6px}
.sc-num{display:inline-flex;align-items:center;justify-content:center;width:28px;height:28px;border-radius:99px;
  background:#F2690F;color:#fff;font-weight:800;font-size:.9rem;flex:none}
.sc-step span{color:#B9C8DC;font-size:.92rem;line-height:1.45}
/* motion: hero fades in, truck drives in then idles, cards rise one after another */
@keyframes scFadeUp{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:none}}
@keyframes scDrive{0%{opacity:0;transform:translateX(-70px)}70%{opacity:1;transform:translateX(6px)}100%{opacity:1;transform:none}}
@keyframes scIdle{0%,100%{transform:translateY(0)}50%{transform:translateY(-3px)}}
.sc-hero{animation:scFadeUp .6s ease-out both}
.sc-truck{animation:scDrive 1.1s cubic-bezier(.2,.8,.2,1) .25s both,scIdle 3.2s ease-in-out 1.5s infinite}
.sc-step{animation:scFadeUp .5s ease-out both;transition:transform .2s,border-color .2s,box-shadow .2s}
.sc-step:nth-child(2){animation-delay:.1s}.sc-step:nth-child(3){animation-delay:.2s}
.sc-step:hover{transform:translateY(-3px);border-color:#F2690F;box-shadow:0 12px 26px rgba(0,0,0,.28)}
@media (prefers-reduced-motion:reduce){.sc-hero,.sc-truck,.sc-step,.sc-banner,.sc-carrier{animation:none!important;transition:none!important}}
</style>
"""

# The illustration is an image: st.html's sanitiser removes inline <svg>, but allows data-URI images.
_TRUCK_FILE = Path(__file__).resolve().parent.parent / "assets" / "hero-truck.svg"
_TRUCK = (f'<img class="sc-truck" alt="" src="data:image/svg+xml;base64,'
          f'{base64.b64encode(_TRUCK_FILE.read_bytes()).decode()}">')


def hero(kicker: str, title_html: str, subtitle: str, chips: list[str]):
    chip_html = "".join(f'<span class="sc-chip">{c}</span>' for c in chips)
    st.html(f"""{_CSS}<div class="sc-hero"><div class="sc-hero-text"><span class="sc-kicker">{kicker}</span>
        <h1>{title_html}</h1><p>{subtitle}</p><div class="sc-chips">{chip_html}</div></div>{_TRUCK}</div>""")


def steps(items: list[tuple[str, str]]):
    """Numbered step cards: [(title, text)]."""
    cards = "".join(f'<div class="sc-step"><b><span class="sc-num">{n}</span>{t}</b><span>{d}</span></div>'
                    for n, (t, d) in enumerate(items, 1))
    st.html(f'{_CSS}<div class="sc-steps">{cards}</div>')


def how_to(page_key: str, items: list[tuple[str, str]]):
    """'How to use this page' guide; open the first time a page is visited in a session."""
    first = f"seen-{page_key}" not in st.session_state
    st.session_state[f"seen-{page_key}"] = True
    with st.expander("How to use this page", icon=":material/lightbulb:", expanded=first):
        steps(items)


def page_title(title: str, subtitle: str):
    st.title(title)
    st.caption(subtitle)


GLOBAL_CSS = """<style>
/* hide the hosting toolbar (Fork / GitHub / developer menu): not part of ShipCheck */
[data-testid='stToolbarActions'],[data-testid='stMainMenu']{display:none !important}
/* buttons lift slightly on hover */
[data-testid='stBaseButton-primary'],[data-testid='stBaseButton-secondary'],[data-testid='stPopoverButton']
  {transition:transform .15s ease,box-shadow .15s ease}
[data-testid='stBaseButton-primary']:hover,[data-testid='stPopoverButton']:hover
  {transform:translateY(-1px);box-shadow:0 8px 20px rgba(242,105,15,.35)}
[data-testid='stBaseButton-secondary']:hover{transform:translateY(-1px)}
[data-testid='stExpander'] details{transition:border-color .2s}
[data-testid='stExpander'] details:hover{border-color:#F2690F}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
</style>"""


def global_style():
    st.html(GLOBAL_CSS)


# ---- Results: status banner and carrier cards ---------------------------------------------

_RESULT_CSS = """<style>
.sc-banner{display:flex;gap:16px;align-items:center;border-radius:18px;padding:18px 20px;margin:2px 0 6px;
  border:1px solid;animation:scFadeUp .45s ease-out both}
.sc-banner .sc-ico{flex:none;width:52px;height:52px;border-radius:99px;display:flex;align-items:center;
  justify-content:center;font-size:1.6rem;font-weight:800;color:#fff}
.sc-banner .sc-kick{font-size:.8rem;font-weight:700;letter-spacing:.06em;text-transform:uppercase;opacity:.85}
.sc-banner .sc-ttl{font-family:'Plus Jakarta Sans',Inter,sans-serif;font-size:1.45rem;font-weight:800;color:#fff;line-height:1.2}
.sc-banner .sc-sub{color:#B9C8DC;font-size:.92rem;margin-top:2px}
.sc-Ready{background:linear-gradient(135deg,rgba(46,204,113,.18),rgba(46,204,113,.05));border-color:rgba(46,204,113,.45)}
.sc-Ready .sc-ico{background:#2ECC71}.sc-Ready .sc-kick{color:#7BE3A6}
.sc-Warnings{background:linear-gradient(135deg,rgba(255,159,67,.2),rgba(255,159,67,.05));border-color:rgba(255,159,67,.5)}
.sc-Warnings .sc-ico{background:#FF9F43}.sc-Warnings .sc-kick{color:#FFC48C}
.sc-Blocked{background:linear-gradient(135deg,rgba(255,90,95,.2),rgba(255,90,95,.05));border-color:rgba(255,90,95,.5)}
.sc-Blocked .sc-ico{background:#FF5A5F}.sc-Blocked .sc-kick{color:#FF9EA1}
.sc-carriers{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:14px;margin:4px 0 8px}
.sc-carrier{position:relative;background:#12243D;border:1px solid #22406A;border-radius:16px;padding:18px 18px 14px;
  animation:scFadeUp .45s ease-out both;transition:transform .2s,box-shadow .2s}
.sc-carrier:hover{transform:translateY(-3px);box-shadow:0 12px 26px rgba(0,0,0,.28)}
.sc-carrier.sc-win{border:2px solid #F2690F;background:linear-gradient(160deg,rgba(242,105,15,.16),#12243D 55%)}
.sc-carrier:nth-child(2){animation-delay:.1s}
.sc-rib{display:inline-block;font-size:.72rem;font-weight:800;letter-spacing:.06em;text-transform:uppercase;
  padding:3px 10px;border-radius:99px;background:#F2690F;color:#fff;margin-bottom:8px}
.sc-rib.sc-alt{background:#22406A;color:#B9C8DC}
.sc-rib.sc-bad{background:rgba(255,90,95,.18);color:#FF9EA1}
.sc-carrier.sc-out{opacity:.62}
.sc-cnote{margin-top:10px;font-size:.84rem;color:#B9C8DC;border-top:1px dashed #22406A;padding-top:8px}
.sc-cnote-bad{color:#FF9EA1}
.sc-cname{font-family:'Plus Jakarta Sans',Inter,sans-serif;font-weight:800;font-size:1.2rem;color:#fff}
.sc-csvc{color:#8DA2BE;font-size:.88rem;margin-bottom:8px}
.sc-cprice{font-family:'Plus Jakarta Sans',Inter,sans-serif;font-weight:800;font-size:clamp(1.35rem,3.6vw,1.9rem);
  color:#fff;white-space:nowrap}
.sc-cprice small{font-size:.85rem;color:#8DA2BE;font-weight:600}
.sc-cstats{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}
.sc-cstats span{font-size:.82rem;color:#EAF0F7;background:rgba(255,255,255,.06);border:1px solid #22406A;
  padding:4px 9px;border-radius:99px}
</style>"""

_ICON = {"Ready": "✓", "Warnings": "!", "Blocked": "✕"}


def status_banner(ev):
    """Big coloured banner: booking, plain-English status, route."""
    from html import escape
    b = ev.booking
    reds = sum(i.severity == "Red" for i in ev.issues)
    ambers = len(ev.issues) - reds
    title = {"Ready": "Ready to ship — all 10 checks pass",
             "Warnings": f"Ready, with {ambers} warning{'s' if ambers != 1 else ''} to check",
             "Blocked": f"Blocked — {reds} issue{'s' if reds != 1 else ''} to fix before shipping"}[ev.status]
    kicker = f"{b.booking_id or 'New booking'} · {b.seller_name or 'Seller not set'}"
    sub = (f"{b.origin_city or '?'} → {b.destination_city or '?'}, {b.destination_country or '?'} · "
           f"{(b.destination_type or '?').lower()} · ready {b.ready_date.strftime('%d-%m-%Y') if b.ready_date else '?'}"
           f" · {(b.seller_priority or '?').lower()} option")
    st.html(f"""{_CSS}{_RESULT_CSS}<div class="sc-banner sc-{ev.status}"><div class="sc-ico">{_ICON[ev.status]}</div>
        <div><div class="sc-kick">{escape(kicker)}</div><div class="sc-ttl">{escape(title)}</div>
        <div class="sc-sub">{escape(sub)}</div></div></div>""")


def _versus(r, win) -> str:
    """How this carrier compares with the recommended one: '+£120 · 2 days faster · +3 pts on time'."""
    parts = []
    dc = (r.total_cost or 0) - (win.total_cost or 0)
    if abs(dc) > 0.005:
        parts.append(f"{'+' if dc > 0 else '−'}£{abs(dc):,.0f}")
    dd = r.option.transit_days - win.option.transit_days
    if dd:
        parts.append(f"{abs(dd):g} day{'s' if abs(dd) != 1 else ''} {'slower' if dd > 0 else 'faster'}")
    dr = r.option.on_time_rate - win.option.on_time_rate
    if dr:
        parts.append(f"{'+' if dr > 0 else '−'}{abs(dr):g} pts on time")
    return " · ".join(parts) or "same cost, speed and reliability"


def carrier_cards(rec):
    """Every carrier on the route side by side: the recommended one first, ruled-out ones greyed."""
    from html import escape
    win = rec.winner
    cards = []
    for r in rec.all_options:
        o = r.option
        out = r.status == "Eliminated"
        tag = {"Recommended": "Recommended", "Runner-up": "Runner-up", "Eligible": "Option"}.get(r.status, "Ruled out")
        cls = " sc-win" if r.status == "Recommended" else " sc-out" if out else ""
        rib = "" if r.status == "Recommended" else " sc-bad" if out else " sc-alt"
        if out:
            note = f'<div class="sc-cnote sc-cnote-bad">{escape(r.reason)}</div>'
        elif win is not None and r is not win:
            note = f'<div class="sc-cnote">vs {escape(win.option.carrier)}: {escape(_versus(r, win))}</div>'
        else:
            note = ""
        cards.append(
            f'<div class="sc-carrier{cls}"><span class="sc-rib{rib}">{tag}</span>'
            f'<div class="sc-cname">{escape(o.carrier)}</div><div class="sc-csvc">{escape(o.service)}</div>'
            f'<div class="sc-cprice">£{(r.total_cost or 0):,.2f} <small>total</small></div>'
            f'<div class="sc-cstats"><span>⏱ {o.transit_days:g} days</span><span>🎯 {o.on_time_rate:g}% on time</span>'
            f'<span>⚖ max {o.max_weight_per_pallet_kg:,.0f} kg/pallet</span></div>{note}</div>')
    st.html(f'{_CSS}{_RESULT_CSS}<div class="sc-carriers">{"".join(cards)}</div>')

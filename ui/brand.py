"""Oops-Proof look and feel: hero banner, step cards and the per-page "How to use" guide.

Custom HTML is used only where Streamlit has no native element (the hero banner and
the numbered step cards). Class names are prefixed "sc-" so the CSS can't leak.
"""
from __future__ import annotations


import html

import streamlit as st

from ui import mascot

_CSS = """
<style>
""" + mascot.CSS + """
.sc-hero{display:flex;flex-wrap:wrap;align-items:center;gap:18px 28px;overflow:hidden;border-radius:22px;padding:34px 34px 30px;
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
.sc-hero-text{flex:1 1 420px;min-width:0}
@media (max-width:760px){.sc-hero{padding:24px 20px}.sc-hero h1{font-size:1.8rem}}
.sc-steps{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:14px;margin:4px 0}
.sc-step{background:#12243D;border:1px solid #22406A;border-radius:16px;padding:16px 16px 14px}
.sc-step b{display:flex;align-items:center;gap:10px;font-size:1.02rem;color:#fff;margin-bottom:6px}
.sc-num{display:inline-flex;align-items:center;justify-content:center;width:28px;height:28px;border-radius:99px;
  background:#F2690F;color:#fff;font-weight:800;font-size:.9rem;flex:none}
.sc-step span{color:#B9C8DC;font-size:.92rem;line-height:1.45}
/* motion: one calm entrance (keyframes live in GLOBAL_CSS), no loops. Lines of the hero glide in
   one after another, the truck drives in once and parks, then the step cards follow. */
.sc-hero{animation:scFade .8s ease-out both}
.sc-hero-text>*{animation:scFadeUp .9s cubic-bezier(.22,1,.36,1) both}
.sc-hero-text>*:nth-child(1){animation-delay:.1s}.sc-hero-text>*:nth-child(2){animation-delay:.2s}
.sc-hero-text>*:nth-child(3){animation-delay:.3s}.sc-hero-text>*:nth-child(4){animation-delay:.4s}
.sc-step{animation:scFadeUp .8s cubic-bezier(.22,1,.36,1) .5s both;
  transition:transform .35s cubic-bezier(.22,1,.36,1),border-color .35s,box-shadow .35s}
.sc-step:nth-child(2){animation-delay:.6s}.sc-step:nth-child(3){animation-delay:.7s}
.sc-step:hover{transform:translateY(-4px);border-color:#F2690F;box-shadow:0 16px 32px rgba(0,0,0,.3)}
/* hero right side: the 3D mascot looking at the booking card */
.sc-side{flex:1 1 560px;max-width:680px;position:relative;min-height:440px}
.sc-side .sc-pv{position:absolute;right:0;top:56px;width:318px;font-size:.8rem;z-index:2}
/* the carton gets its own space left of the card, so the card can never cover it */
@media (min-width:761px){.sc-side .sc-mascot{right:330px}}
@media (max-width:760px){.sc-side{flex-basis:100%;min-height:0;display:flex;flex-direction:column;gap:6px}
  .sc-side .sc-pv{position:relative;width:auto}}
@media (max-width:480px){.sc-pv{padding:14px}.sc-pv-val{font-size:.74rem}.sc-pv-row{gap:6px}}
/* the live example card: BK-105 fixes itself on a 10 s loop (blocked -> cursor taps the fix -> confetti ->
   ready to ship -> reset). The 3D mascot reads this loop's clock to stay in step. */
.sc-pv{max-width:100%;background:#0F1F35;border:1px solid #2A4A75;border-radius:18px;padding:16px 18px;position:relative;
  box-shadow:0 24px 60px rgba(0,0,0,.35);font-size:.84rem;color:#D5DEEA;overflow:visible;
  animation:scFadeUp .9s cubic-bezier(.22,1,.36,1) .35s both}
.sc-pv-live{display:inline-flex;align-items:center;gap:6px;font-size:.66rem;font-weight:800;letter-spacing:.08em;
  text-transform:uppercase;color:#9FB0C6;margin-bottom:8px}
.sc-pv-live i{width:7px;height:7px;border-radius:50%;background:#FF5A5F;box-shadow:0 0 0 0 rgba(255,90,95,.6);
  animation:scLive 1.6s ease-out infinite}
@keyframes scLive{to{box-shadow:0 0 0 8px rgba(255,90,95,0)}}
.sc-pv-top{display:flex;justify-content:space-between;align-items:center;gap:10px;margin-bottom:10px}
.sc-pv-id{font-family:'Plus Jakarta Sans',Inter,sans-serif;font-weight:800;color:#fff;font-size:1.25rem;line-height:1}
.sc-pv-sub{color:#8FA3BD;font-size:.76rem;margin-top:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.sc-pill{font-size:.7rem;font-weight:700;padding:4px 10px;border-radius:99px;white-space:nowrap}
.sc-red{background:rgba(255,90,95,.16);color:#FF9EA1;border:1px solid rgba(255,90,95,.4)}
.sc-green{background:rgba(46,204,113,.16);color:#7BE3A6;border:1px solid rgba(46,204,113,.45)}
.sc-pv-row{display:grid;grid-template-columns:16px 1fr auto;gap:8px;align-items:center;padding:6px 0;border-top:1px solid #1E3352}
.sc-pv-rule{color:#B9C8DC;white-space:nowrap}
.sc-pv-val{font-variant-numeric:tabular-nums;color:#fff;text-align:right;white-space:nowrap}
.sc-x{color:#FF7A7E;font-weight:800}.sc-ok{color:#5BD98C;font-weight:800}
.sc-pv-cause{position:relative;margin-top:10px;background:rgba(242,105,15,.08);border:1px solid rgba(242,105,15,.3);
  border-radius:12px;padding:10px 12px;animation:scCause 10s ease infinite}
.sc-pv-kick{font-size:.66rem;font-weight:800;letter-spacing:.06em;text-transform:uppercase;color:#FF9A4D;margin-bottom:3px}
.sc-pv-btnwrap{position:relative;display:inline-block;margin-top:8px}
.sc-pv-btn{display:inline-grid;font-weight:700;font-size:.76rem;border-radius:8px;overflow:hidden;animation:scPress 10s ease infinite}
.sc-pv-btn>*{grid-area:1/1;padding:6px 12px}
.sc-pv-btn .sc-a{background:#F2690F;color:#fff}.sc-pv-btn .sc-b{background:#2ECC71;color:#0E1B2E}
.sc-pv-foot{margin-top:10px;color:#8FA3BD;font-size:.78rem}
.sc-pv-foot .sc-b{color:#B9E8CB}
.sc-sw{display:grid}.sc-sw>*{grid-area:1/1}
.sc-a{animation:scA 10s ease infinite}.sc-b{animation:scB 10s cubic-bezier(.34,1.56,.64,1) infinite}
.sc-pill.sc-b{animation:scB 10s cubic-bezier(.34,1.56,.64,1) infinite,scGlow 10s ease infinite}
/* a little cursor glides in and taps the fix */
.sc-tap{position:absolute;left:58%;top:62%;width:18px;height:18px;margin:-9px 0 0 -9px;border-radius:50%;pointer-events:none;
  background:rgba(255,255,255,.95);border:3px solid #F2690F;box-shadow:0 3px 10px rgba(0,0,0,.4);animation:scTap 10s ease infinite}
.sc-tap::after{content:"";position:absolute;inset:-3px;border-radius:50%;border:2px solid #FF8A3D;opacity:0;animation:scRing 10s ease-out infinite}
/* confetti from the button when it's fixed */
.sc-conf{position:absolute;left:50%;top:50%;width:7px;height:7px;border-radius:2px;opacity:0;pointer-events:none;animation:scConf 10s ease-out infinite}
@keyframes scA{0%,37%{opacity:1;transform:none}41%,95%{opacity:0;transform:translateY(-5px)}99%,100%{opacity:1;transform:none}}
@keyframes scB{0%,37%{opacity:0;transform:translateY(5px) scale(.9)}43%,94%{opacity:1;transform:none}98%,100%{opacity:0;transform:translateY(5px) scale(.9)}}
@keyframes scGlow{0%,41%{box-shadow:0 0 0 0 rgba(46,204,113,0)}46%{box-shadow:0 0 0 6px rgba(46,204,113,.35)}
  56%,100%{box-shadow:0 0 0 0 rgba(46,204,113,0)}}
@keyframes scCause{0%{opacity:.35}5%,100%{opacity:1}}
@keyframes scPress{0%,34%,40%,100%{transform:none;filter:none}37%{transform:scale(.92);filter:brightness(.85)}}
@keyframes scTap{0%,19%{opacity:0;transform:translate(120px,80px)}23%{opacity:1}33%{transform:translate(0,0)}
  37%{transform:translate(0,0) scale(.75)}39%{transform:translate(0,0) scale(1)}46%{opacity:1;transform:translate(0,0)}
  54%,100%{opacity:0;transform:translate(70px,60px)}}
@keyframes scRing{0%,36%{opacity:0;transform:scale(1)}37%{opacity:1;transform:scale(1)}46%,100%{opacity:0;transform:scale(2.6)}}
@keyframes scConf{0%,38%{opacity:0;transform:translate(-50%,-50%) scale(.3)}40%{opacity:1}
  50%{opacity:1;transform:translate(calc(-50% + var(--x)),calc(-50% + var(--y))) rotate(var(--r)) scale(1)}
  55%,100%{opacity:0;transform:translate(calc(-50% + var(--x)),calc(-50% + var(--y) + 18px)) rotate(var(--r))}}
@media (prefers-reduced-motion:reduce){.sc-a,.sc-tap,.sc-conf{display:none}.sc-b{opacity:1;animation:none}
  .sc-pv-cause,.sc-pv-foot,.sc-pv-btn{animation:none}}
@media (prefers-reduced-motion:reduce){.sc-hero,.sc-step,.sc-banner,.sc-carrier{animation:none!important;transition:none!important}}
</style>
"""

# The illustration is an image: st.html's sanitiser removes inline <svg>, but allows data-URI images.
# A product preview instead of an illustration: BK-105 from the organisers' sample, playing once:
# two Red checks, the root cause, a one-tap fix, then Ready to ship. Plain HTML/CSS (st.html strips SVG).
_PREVIEW = """<div class="sc-pv" aria-label="Live example: booking BK-105 goes from blocked to ready to ship after one fix">
 <div class="sc-pv-live"><i></i>Live example</div>
 <div class="sc-pv-top"><div style="min-width:0"><div class="sc-pv-id">BK-105</div>
  <div class="sc-pv-sub">Highland Knitwear · London → Lyon</div></div>
  <div class="sc-sw"><span class="sc-pill sc-red sc-a">Blocked · 2 issues</span><span class="sc-pill sc-green sc-b">✓ Ready to ship</span></div></div>
 <div class="sc-pv-row"><div class="sc-sw"><span class="sc-x sc-a">✕</span><span class="sc-ok sc-b">✓</span></div>
  <div class="sc-pv-rule">R-03 Packing</div>
  <div class="sc-sw sc-pv-val"><span class="sc-a">24 × 45 ≠ 1,200</span><span class="sc-b">24 × 50 = 1,200</span></div></div>
 <div class="sc-pv-row"><div class="sc-sw"><span class="sc-x sc-a">✕</span><span class="sc-ok sc-b">✓</span></div>
  <div class="sc-pv-rule">R-04 Carton total</div>
  <div class="sc-sw sc-pv-val"><span class="sc-a">75 ≠ 80</span><span class="sc-b">80 = 80</span></div></div>
 <div class="sc-pv-cause"><div class="sc-pv-kick">Root cause · high confidence</div>
  <div>SOCK-01 cartons should be <b>50</b>, not 45</div>
  <div class="sc-pv-btnwrap"><div class="sc-pv-btn"><span class="sc-a">Set cartons to 50</span><span class="sc-b">✓ Fixed</span></div>
   <i class="sc-conf" style="--x:-46px;--y:-38px;--r:120deg;background:#FF8A3D"></i><i class="sc-conf" style="--x:-22px;--y:-56px;--r:-80deg;background:#2ECC71"></i><i class="sc-conf" style="--x:6px;--y:-62px;--r:200deg;background:#F2C744"></i><i class="sc-conf" style="--x:34px;--y:-50px;--r:-140deg;background:#7DB4FF"></i><i class="sc-conf" style="--x:54px;--y:-26px;--r:90deg;background:#FF5A5F"></i><i class="sc-conf" style="--x:-58px;--y:-6px;--r:-60deg;background:#2ECC71"></i><i class="sc-conf" style="--x:60px;--y:4px;--r:160deg;background:#F2C744"></i><i class="sc-conf" style="--x:-30px;--y:18px;--r:40deg;background:#FF8A3D"></i><span class="sc-tap"></span></div></div>
 <div class="sc-pv-foot sc-sw"><span class="sc-a">Fix it to see the best carrier</span><span class="sc-b">Recommended: Carrier B · £210 · 3 days</span></div>
</div>"""


def hero(kicker: str, title_html: str, subtitle: str, chips: list[str]):
    chip_html = "".join(f'<span class="sc-chip">{c}</span>' for c in chips)
    st.html(f"""{_CSS}<div class="sc-hero"><div class="sc-hero-text"><span class="sc-kicker">{kicker}</span>
        <h1>{title_html}</h1><p>{subtitle}</p><div class="sc-chips">{chip_html}</div></div>
        <div class="sc-side">{mascot.HTML}{_PREVIEW}</div></div>""")
    st.html(mascot.JS, unsafe_allow_javascript=True)


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
/* hide the hosting toolbar (Fork / GitHub / developer menu): not part of Oops-Proof */
[data-testid='stToolbarActions'],[data-testid='stMainMenu']{display:none !important}
/* buttons lift slightly on hover */
[data-testid='stBaseButton-primary'],[data-testid='stBaseButton-secondary'],[data-testid='stPopoverButton']
  {transition:transform .3s cubic-bezier(.22,1,.36,1),box-shadow .3s cubic-bezier(.22,1,.36,1)}
[data-testid='stBaseButton-primary']:hover,[data-testid='stPopoverButton']:hover
  {transform:translateY(-1px);box-shadow:0 8px 20px rgba(242,105,15,.35)}
[data-testid='stBaseButton-secondary']:hover{transform:translateY(-1px)}
[data-testid='stExpander'] details{transition:border-color .2s}
[data-testid='stExpander'] details:hover{border-color:#F2690F}
/* layout: Ask AI sits in the top navigation bar, so the page starts right under it */
.st-key-ask-ai{position:fixed;top:.55rem;right:1.25rem;z-index:999991;width:auto !important}
[data-testid='stMainBlockContainer']{padding-top:4.25rem}
@media (max-width:640px){[data-testid='stMainBlockContainer']{padding-top:3.75rem}.st-key-ask-ai{right:.75rem}}
/* calmer page titles in the brand typeface */
[data-testid='stHeading'] h1{font-family:'Plus Jakarta Sans',Inter,sans-serif;font-size:2.1rem;font-weight:800;
  letter-spacing:-.02em;line-height:1.15;padding-bottom:.15rem}
[data-testid='stHeading'] h2,[data-testid='stHeading'] h3{font-family:'Plus Jakarta Sans',Inter,sans-serif;letter-spacing:-.01em}
[data-testid='stCaptionContainer']{color:#9FB0C6}
/* shared motion: a soft rise that sharpens from a slight blur, on an ease-out curve that settles */
@keyframes scFadeUp{from{opacity:0;transform:translateY(16px);filter:blur(4px)}to{opacity:1;transform:none;filter:none}}
@keyframes scFade{from{opacity:0}to{opacity:1}}
@keyframes scDrive{from{opacity:0;transform:translateX(-110px)}to{opacity:1;transform:none}}
/* no grey flicker while the page updates after a click */
[data-stale='true']{opacity:1 !important;transition:none !important}
html{scroll-behavior:smooth}
@media (prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}html{scroll-behavior:auto}}
</style>"""


def global_style():
    st.html(GLOBAL_CSS)


# ---- Results: status banner and carrier cards ---------------------------------------------

_RESULT_CSS = """<style>
.sc-banner{display:flex;gap:16px;align-items:center;border-radius:18px;padding:18px 20px;margin:2px 0 6px;
  border:1px solid;animation:scFadeUp .7s cubic-bezier(.22,1,.36,1) both}
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
  animation:scFadeUp .7s cubic-bezier(.22,1,.36,1) both;
  transition:transform .35s cubic-bezier(.22,1,.36,1),box-shadow .35s}
.sc-carrier:hover{transform:translateY(-4px);box-shadow:0 16px 32px rgba(0,0,0,.3)}
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


# ---- Chat: the live booking as a checklist --------------------------------------------------

_CHECKLIST_CSS = """<style>
.sc-ck-bar{display:flex;align-items:center;gap:10px;margin:2px 0 10px;font-size:.8rem;color:#9FB0C6}
.sc-ck-track{flex:1;height:6px;border-radius:99px;background:#1E3352;overflow:hidden}
.sc-ck-fill{height:100%;border-radius:99px;background:linear-gradient(90deg,#F2690F,#FF8A3D);
  transition:width .6s cubic-bezier(.22,1,.36,1)}
.sc-ck{display:grid;grid-template-columns:20px 112px 1fr;gap:4px 8px;align-items:baseline;font-size:.9rem}
.sc-ck i{font-style:normal;font-weight:800;text-align:center}
.sc-ck .d{color:#5BD98C}.sc-ck .c{color:#7DB4FF}.sc-ck .t{color:#4A6283}
.sc-ck .l{color:#9FB0C6}.sc-ck .v{color:#fff;font-weight:600}.sc-ck .m{color:#5D7392}
</style>"""


def booking_checklist(rows: list[tuple[str, object, object]], to_confirm: set[str]):
    """rows: (label, value or None, field). Done ✓, to confirm (blue), still to go ○, with a progress bar."""
    done = sum(1 for _, v, f in rows if v not in (None, "") and f not in to_confirm)
    cells = []
    for label, value, field in rows:
        if value in (None, ""):
            mark, val = '<i class="t">○</i>', '<span class="m">to go</span>'
        elif field in to_confirm:
            mark, val = '<i class="c">◐</i>', f'<span class="v">{html.escape(str(value))}</span> <span class="c">· to confirm</span>'
        else:
            mark, val = '<i class="d">✓</i>', f'<span class="v">{html.escape(str(value))}</span>'
        cells.append(f'{mark}<span class="l">{html.escape(label)}</span><span>{val}</span>')
    pct = round(100 * done / len(rows)) if rows else 0
    return (f'{_CHECKLIST_CSS}<div class="sc-ck-bar"><span>{done} of {len(rows)} details</span>'
            f'<div class="sc-ck-track"><div class="sc-ck-fill" style="width:{pct}%"></div></div></div>'
            f'<div class="sc-ck">{"".join(cells)}</div>')


# ---- The 10-rule scorecard for one booking -----------------------------------------------------

_RULE_CSS = """<style>
.sc-rules-head{display:flex;align-items:baseline;gap:10px;margin:2px 0 8px;font-size:.95rem;color:#B9C8DC}
.sc-rules-head b{font-family:'Plus Jakarta Sans',Inter,sans-serif;font-size:1.15rem;color:#fff}
.sc-rules{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:8px;margin-bottom:10px}
@media (max-width:760px){.sc-rules{grid-template-columns:repeat(2,minmax(0,1fr))}}
.sc-rule{display:flex;align-items:center;gap:8px;padding:8px 10px;border-radius:12px;border:1px solid;font-size:.82rem;
  line-height:1.2;min-width:0}
.sc-rule i{flex:none;width:20px;height:20px;border-radius:99px;display:flex;align-items:center;justify-content:center;
  font-style:normal;font-weight:800;font-size:.75rem}
.sc-rule span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.sc-rule b{display:block;font-size:.72rem;letter-spacing:.04em;opacity:.85}
.sc-rule.pass{background:rgba(46,204,113,.08);border-color:rgba(46,204,113,.35);color:#CFEFDC}.sc-rule.pass i{background:#2ECC71;color:#0E1B2E}
.sc-rule.red{background:rgba(255,90,95,.10);border-color:rgba(255,90,95,.5);color:#FFD2D3}.sc-rule.red i{background:#FF5A5F;color:#fff}
.sc-rule.amber{background:rgba(255,159,67,.10);border-color:rgba(255,159,67,.5);color:#FFE2C4}.sc-rule.amber i{background:#FF9F43;color:#0E1B2E}
.sc-rule.unchecked{background:rgba(255,255,255,.03);border-color:#2A4A75;color:#8FA3BD}.sc-rule.unchecked i{background:#2A4A75;color:#B9C8DC}
</style>"""
RULE_MARK = {"pass": ("✓", "passed"), "red": ("✕", "broken"), "amber": ("!", "warning"), "unchecked": ("–", "not checked: data missing")}


def rule_chips(score: list[dict]) -> str:
    """'Rule check · 8 of 10 passed' and one chip per rule (R-01 … R-10)."""
    passed = sum(r["state"] == "pass" for r in score)
    chips = "".join(f'<div class="sc-rule {r["state"]}" title="{r["rule"]} {r["name"]}: {RULE_MARK[r["state"]][1]}">'
                    f'<i>{RULE_MARK[r["state"]][0]}</i><span><b>{r["rule"]}</b>{html.escape(r["name"])}</span></div>'
                    for r in score)
    unchecked = sum(r["state"] == "unchecked" for r in score)
    note = f" · {unchecked} not checked (data missing)" if unchecked else ""
    return (f'{_RULE_CSS}<div class="sc-rules-head"><b>{passed} of 10 rules passed</b>'
            f'<span>Rule check{note}</span></div><div class="sc-rules">{chips}</div>')

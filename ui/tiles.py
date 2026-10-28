"""The upload page's three status cards: Can't ship yet / Warnings / Ready to ship.

Each card is bold and animated (the number pops in, a share bar fills, the icon moves) and is a real
button: tapping it filters the bookings table to that status, tapping it again shows everything. When a
fix changes a count, that card's new number pops in next to a fading 'was N'.
"""
from __future__ import annotations

import streamlit as st

# status -> (css name, icon, label, empty-state line)
TILES = {"Blocked": ("blocked", "✕", "Can't ship yet", "Nothing blocked 🎉"),
         "Warnings": ("warn", "!", "Warnings", "No warnings 🎉"),
         "Ready": ("ready", "✓", "Ready to ship", "None ready yet")}
WORDS = {"Blocked": "can't ship yet", "Warnings": "with warnings", "Ready": "ready to ship"}

_CSS = """<style>
.sc-tile{--c:#FF5A5F;--soft:255,90,95;position:relative;overflow:hidden;border-radius:18px;padding:14px 16px 12px;
  background:radial-gradient(120% 140% at 0% 0%,rgba(var(--soft),.30),rgba(var(--soft),.06) 55%,#10213A 100%);
  border:1px solid rgba(var(--soft),.55);box-shadow:0 10px 30px rgba(var(--soft),.16),inset 0 1px 0 rgba(255,255,255,.06);
  color:#E8EEF6;transition:transform .25s cubic-bezier(.22,1,.36,1),box-shadow .25s,border-color .25s;min-height:132px}
.sc-tile.warn{--c:#FF9F43;--soft:255,159,67}
.sc-tile.ready{--c:#2ECC71;--soft:46,204,113}
.sc-tile.zero{background:#10213A;border-color:#24406A;box-shadow:none}
.sc-tile.zero .sc-t-ico{background:#1E3352;color:#6F84A1;box-shadow:none;animation:none}
.sc-tile.zero .sc-t-num{color:#6F84A1}
.sc-t-top{display:flex;align-items:center;justify-content:space-between;gap:8px}
.sc-t-ico{width:34px;height:34px;border-radius:11px;display:grid;place-items:center;font-weight:900;font-size:1.05rem;
  background:var(--c);color:#0E1B2E;box-shadow:0 4px 14px rgba(var(--soft),.45)}
.sc-tile.blocked .sc-t-ico{animation:scTShake 4s ease-in-out 1.2s infinite}
.sc-tile.warn .sc-t-ico{animation:scTBlink 2.4s ease-in-out infinite}
.sc-tile.ready .sc-t-ico{animation:scTHop 3s cubic-bezier(.34,1.56,.64,1) 1s infinite}
.sc-t-tag{font-size:.64rem;font-weight:800;letter-spacing:.08em;text-transform:uppercase;color:rgba(255,255,255,.55);
  white-space:nowrap;transition:color .2s}
.sc-t-num{font-family:'Plus Jakarta Sans',Inter,sans-serif;font-weight:800;font-size:2.6rem;line-height:1;margin-top:10px;
  color:var(--c);font-variant-numeric:tabular-nums;transform-origin:left bottom}
.sc-t-lab{font-weight:700;font-size:.92rem;color:#fff;margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.sc-t-bar{height:6px;border-radius:99px;background:rgba(255,255,255,.08);margin-top:10px;overflow:hidden}
.sc-t-bar i{display:block;height:100%;border-radius:inherit;transform-origin:left;
  background:linear-gradient(90deg,rgba(var(--soft),.55),var(--c));box-shadow:0 0 10px rgba(var(--soft),.7)}
.sc-t-foot{font-size:.72rem;color:#9FB0C6;margin-top:6px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.sc-tile::before{content:"";position:absolute;inset:0;pointer-events:none;
  background:linear-gradient(105deg,transparent 35%,rgba(255,255,255,.13) 50%,transparent 65%);transform:translateX(-120%)}
/* first view: cards rise in one after another, numbers pop in, bars fill, a shine sweeps across */
.sc-tile.intro{animation:scFadeUp .7s cubic-bezier(.22,1,.36,1) var(--d) both}
.sc-tile.intro .sc-t-num{animation:scTIn .8s cubic-bezier(.34,1.56,.64,1) calc(var(--d) + .2s) both}
.sc-tile.intro .sc-t-bar i{animation:scTBar 1.4s cubic-bezier(.22,1,.36,1) calc(var(--d) + .25s) both}
.sc-tile.intro::before{animation:scTShine 1.1s ease calc(var(--d) + .9s) both}
/* a count changed after a fix: the old number slides out, the new one pops in */
.sc-tile.bump .sc-t-num{animation:scTIn .7s cubic-bezier(.34,1.56,.64,1) both}
.sc-t-old{font-size:.8rem;font-weight:700;color:rgba(255,255,255,.45);margin-left:8px;text-decoration:line-through;vertical-align:middle;font-family:Inter,sans-serif}
.sc-tile.bump .sc-t-old{animation:scTOld 2.4s ease both}
.sc-tile.bump .sc-t-bar i{animation:scTBar .9s cubic-bezier(.22,1,.36,1) both}
.sc-tile.bump{animation:scTRing 1.1s ease-out both}
.sc-tile.bump::before{animation:scTShine .9s ease .2s both}
/* the filter is on */
.sc-tile.on{border-color:var(--c);box-shadow:0 0 0 2px var(--c),0 14px 34px rgba(var(--soft),.35);transform:translateY(-2px)}
.sc-tile.on .sc-t-tag{color:var(--c)}
@keyframes scTIn{0%{opacity:0;transform:translateY(12px) scale(.6)}60%{opacity:1;transform:scale(1.15)}100%{opacity:1;transform:none}}
@keyframes scTBar{from{transform:scaleX(0)}}
@keyframes scTOld{0%,60%{opacity:1}100%{opacity:0}}
@keyframes scTRing{0%{box-shadow:0 0 0 0 rgba(var(--soft),.7)}100%{box-shadow:0 0 0 14px rgba(var(--soft),0)}}
@keyframes scTShine{from{transform:translateX(-120%)}to{transform:translateX(120%)}}
@keyframes scTShake{0%,86%,100%{transform:none}88%{transform:rotate(-12deg)}91%{transform:rotate(10deg)}
  94%{transform:rotate(-6deg)}97%{transform:rotate(3deg)}}
@keyframes scTBlink{0%,100%{box-shadow:0 0 0 0 rgba(var(--soft),.55)}60%{box-shadow:0 0 0 9px rgba(var(--soft),0)}}
@keyframes scTHop{0%,80%,100%{transform:none}86%{transform:translateY(-6px) scale(1.06)}92%{transform:translateY(0) scale(.96)}}
/* the card is a button: an invisible Streamlit button covers it */
[class*="st-key-tilecard-"]{position:relative;gap:0!important}
[class*="st-key-tilebtn-"]{position:absolute!important;inset:0;z-index:3;margin:0!important}
[class*="st-key-tilebtn-"] div,[class*="st-key-tilebtn-"] button{width:100%!important;height:100%!important}
[class*="st-key-tilebtn-"] button{opacity:0;cursor:pointer}
[class*="st-key-tilebtn-"] button:disabled{cursor:default}
[class*="st-key-tilecard-"]:has(button:not(:disabled):hover) .sc-tile:not(.on){transform:translateY(-3px);
  box-shadow:0 16px 36px rgba(var(--soft),.3)}
[class*="st-key-tilecard-"]:has(button:not(:disabled):hover) .sc-t-tag{color:#fff}
[class*="st-key-tilecard-"]:has(button:focus-visible) .sc-tile{outline:2px solid #fff;outline-offset:2px}
[class*="st-key-tilecard-"]:has(button:active) .sc-tile{transform:scale(.98)}
@media (max-width:640px){.sc-tile{padding:11px 11px 10px;min-height:118px;border-radius:15px}
  .sc-t-ico{width:28px;height:28px;border-radius:9px;font-size:.9rem}.sc-t-tag{display:none}
  .sc-t-num{font-size:2rem;margin-top:8px}.sc-t-lab{font-size:.78rem;white-space:normal;line-height:1.15}
  .sc-t-foot{font-size:.66rem}}
@media (prefers-reduced-motion:reduce){.sc-tile,.sc-tile *,.sc-tile::before{animation:none!important;transition:none!important}}
</style>"""


def _toggle(status: str):
    st.session_state.tile_filter = None if st.session_state.get("tile_filter") == status else status
    st.session_state.pop("batch_table", None)           # the old row pick doesn't apply to the new list
    st.session_state.focus_booking = None


def status_tiles(counts: dict[str, int], source: str):
    """Render the three cards for this file. `source` identifies the file, so the intro plays once per file."""
    total = sum(counts.values()) or 1
    seen = st.session_state.get("tile_seen") or {}
    prev = seen.get("counts") if seen.get("source") == source else None
    st.session_state.tile_seen = {"source": source, "counts": dict(counts)}
    active = st.session_state.get("tile_filter")
    with st.container(horizontal=True, gap="small", key="tile-row"):
        for n, (status, (cls, icon, label, empty)) in enumerate(TILES.items()):
            k = counts.get(status, 0)
            share = round(100 * k / total)
            old = (prev or {}).get(status, 0)
            motion = ("intro" if prev is None else "bump" if prev.get(status, 0) != k else "")
            tag = "Filtering ✓" if active == status else "Tap to filter" if k else ""
            foot = f"{k} of {total} · {share}%" if k else empty
            was = f'<span class="sc-t-old">was {old}</span>' if motion == "bump" else ""
            with st.container(key=f"tilecard-{status}"):
                st.html((_CSS if n == 0 else "") + f'<div class="sc-tile {cls} {motion} {"on" if active == status else ""} {"zero" if not k else ""}" '
                        f'style="--d:{n * .12:.2f}s">'
                        f'<div class="sc-t-top"><div class="sc-t-ico">{icon}</div><div class="sc-t-tag">{tag}</div></div>'
                        f'<div class="sc-t-num">{k}{was}</div><div class="sc-t-lab">{label}</div>'
                        f'<div class="sc-t-bar"><i style="width:{share}%"></i></div><div class="sc-t-foot">{foot}</div></div>')
                st.button(f"{label}: {k}", key=f"tilebtn-{status}", on_click=_toggle, args=(status,),
                          disabled=not k and active != status)

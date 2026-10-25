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

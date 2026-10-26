"""The "checking your file" animation: plays once when a file is uploaded, using the real results.

The bookings appear as spreadsheet rows, a scan beam sweeps down them and stamps each row with its
verdict, the steps tick off (reading, rules, root causes, carriers), the totals land, and the overlay
fades into the "What we found" pop-up underneath. About 3.4 s; a tap skips it. CSS animations only,
plus one listener for the tap.
"""
from __future__ import annotations

import html

from core.check import Evaluation

MAX_ROWS = 12
VERDICT = {"Ready": ("ok", "✓"), "Warnings": ("warn", "!"), "Blocked": ("bad", "✕")}
STEPS = [("Reading the Bookings and Items sheets", 0.45), ("Running the 10 rules, R-01 to R-10", 1.55),
         ("Finding root causes", 2.0), ("Choosing carriers by priority", 2.35), ("Report ready", 2.7)]

CSS = """<style>
.sc-scan{position:fixed;inset:0;z-index:2147483000;display:flex;align-items:center;justify-content:center;
  background:rgba(6,14,26,.72);backdrop-filter:blur(6px);font-family:Inter,sans-serif;
  animation:scScanOut .45s ease-in 3.35s forwards}
@keyframes scScanOut{to{opacity:0;visibility:hidden;pointer-events:none}}
.sc-scan-card{width:min(860px,92vw);background:#0F1F35;border:1px solid #2A4A75;border-radius:20px;padding:22px 24px;
  box-shadow:0 30px 80px rgba(0,0,0,.5);color:#D5DEEA;animation:scFadeUp .5s cubic-bezier(.22,1,.36,1) both}
.sc-scan-top{display:flex;justify-content:space-between;align-items:baseline;gap:12px;margin-bottom:12px}
.sc-scan-title{font-family:'Plus Jakarta Sans',Inter,sans-serif;font-weight:800;font-size:1.15rem;color:#fff}
.sc-scan-file{color:#8FA3BD;font-size:.82rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.sc-scan-bar{height:4px;border-radius:99px;background:#1E3352;overflow:hidden;margin-bottom:16px}
.sc-scan-bar i{display:block;height:100%;width:0;background:linear-gradient(90deg,#F2690F,#FF8A3D);
  animation:scGrow 2.6s cubic-bezier(.4,0,.2,1) .15s forwards}
@keyframes scGrow{to{width:100%}}
.sc-scan-body{display:grid;grid-template-columns:1.3fr 1fr;gap:22px}
.sc-sheet{position:relative;border:1px solid #22406A;border-radius:12px;overflow:hidden;font-size:.82rem}
.sc-sheet-row{display:grid;grid-template-columns:76px 1fr 64px;gap:8px;align-items:center;padding:6px 12px;
  border-top:1px solid #1A2E4A;opacity:0;animation:scRowIn .35s ease-out both}
.sc-sheet-row.h{opacity:1;animation:none;border-top:0;background:#16263F;color:#8FA3BD;font-size:.72rem;
  font-weight:700;letter-spacing:.06em;text-transform:uppercase}
@keyframes scRowIn{from{opacity:0;transform:translateX(-6px)}to{opacity:1;transform:none}}
.sc-sheet-row .id{color:#fff;font-weight:600;font-variant-numeric:tabular-nums}
.sc-sheet-row .rt{color:#9FB0C6;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.sc-v{justify-self:center;width:22px;height:22px;border-radius:99px;display:flex;align-items:center;justify-content:center;
  font-weight:800;font-size:.8rem;transform:scale(0);animation:scStamp .35s cubic-bezier(.34,1.56,.64,1) both}
@keyframes scStamp{to{transform:scale(1)}}
.sc-v.ok{background:rgba(46,204,113,.18);color:#5BD98C}.sc-v.warn{background:rgba(255,159,67,.2);color:#FFB36B}
.sc-v.bad{background:rgba(255,90,95,.2);color:#FF7A7E}
.sc-beam{position:absolute;left:0;right:0;top:28px;height:34px;pointer-events:none;
  background:linear-gradient(180deg,transparent,rgba(242,105,15,.28),transparent);border-bottom:2px solid rgba(255,138,61,.8);
  animation:scBeam 1.5s cubic-bezier(.45,0,.55,1) .45s both}
@keyframes scBeam{from{transform:translateY(0);opacity:1}90%{opacity:1}to{transform:translateY(var(--travel));opacity:0}}
.sc-more{padding:6px 12px;color:#8FA3BD;font-size:.76rem;border-top:1px solid #1A2E4A;opacity:0;animation:scRowIn .3s ease-out .9s both}
.sc-steps{display:flex;flex-direction:column;gap:11px;font-size:.88rem}
.sc-step-l{display:flex;align-items:center;gap:10px;color:#6F84A1}
.sc-step-l b{flex:none;width:22px;height:22px;border-radius:99px;border:2px solid #2A4A75;display:flex;align-items:center;
  justify-content:center;font-size:.72rem;color:transparent;animation:scTick .3s ease-out both}
.sc-step-l span{animation:scLit .3s ease-out both}
@keyframes scTick{to{background:#2ECC71;border-color:#2ECC71;color:#0E1B2E}}
@keyframes scLit{to{color:#E8EEF6}}
.sc-step-l.last span{font-weight:700}
.sc-tally{display:flex;gap:10px;margin-top:16px;flex-wrap:wrap}
.sc-tally div{flex:1;min-width:84px;border-radius:12px;padding:10px 12px;background:#12243D;border:1px solid #22406A;
  opacity:0;animation:scFadeUp .5s cubic-bezier(.22,1,.36,1) both}
.sc-tally strong{display:block;font-family:'Plus Jakarta Sans',Inter,sans-serif;font-size:1.5rem;line-height:1.1;color:#fff}
.sc-tally span{font-size:.76rem;color:#9FB0C6}
.sc-tally .bad{border-top:3px solid #FF5A5F}.sc-tally .warn{border-top:3px solid #FF9F43}.sc-tally .ok{border-top:3px solid #2ECC71}
.sc-skip{margin-top:12px;text-align:right;font-size:.72rem;color:#5D7392}
@media (max-width:640px){.sc-scan-body{grid-template-columns:1fr}.sc-steps{display:none}}
@media (prefers-reduced-motion:reduce){.sc-scan{display:none}}
</style>"""

SKIP_JS = """<script>
(() => { const o = document.querySelector('.sc-scan:not([data-bound])'); if (!o) return;
  o.dataset.bound = '1'; o.addEventListener('pointerdown', () => o.remove());
  setTimeout(() => o.remove(), 4200); })();
</script>"""


def overlay(evals: list[Evaluation], file_name: str) -> str:
    shown = evals[:MAX_ROWS]
    span = 1.5 / max(1, len(shown))                       # the beam passes each row in turn
    rows = []
    for i, ev in enumerate(shown):
        b = ev.booking
        cls, mark = VERDICT[ev.status]
        route = f"{b.origin_city or '?'} → {b.destination_city or '?'}"
        rows.append(f'<div class="sc-sheet-row" style="animation-delay:{0.15 + i * 0.05:.2f}s">'
                    f'<span class="id">{html.escape(b.booking_id or "—")}</span><span class="rt">{html.escape(route)}</span>'
                    f'<span class="sc-v {cls}" style="animation-delay:{0.5 + (i + 0.5) * span:.2f}s">{mark}</span></div>')
    more = (f'<div class="sc-more">+ {len(evals) - len(shown)} more bookings</div>' if len(evals) > len(shown) else "")
    steps = "".join(f'<div class="sc-step-l{" last" if n == len(STEPS) - 1 else ""}">'
                    f'<b style="animation-delay:{at:.2f}s">✓</b><span style="animation-delay:{at:.2f}s">{label}</span></div>'
                    for n, (label, at) in enumerate(STEPS))
    count = {s: sum(e.status == s for e in evals) for s in VERDICT}
    tally = "".join(f'<div class="{VERDICT[s][0]}" style="animation-delay:{2.25 + n * 0.12:.2f}s">'
                    f'<strong>{count[s]}</strong><span>{label}</span></div>'
                    for n, (s, label) in enumerate([("Blocked", "can't ship yet"), ("Warnings", "with warnings"),
                                                    ("Ready", "ready to ship")]))
    travel = 30 * (len(shown) - 1) + 6                     # px: one row is ~30 px tall
    return (f'{CSS}<div class="sc-scan" role="status" aria-label="Checking your file">'
            f'<div class="sc-scan-card"><div class="sc-scan-top"><span class="sc-scan-title">Checking your file</span>'
            f'<span class="sc-scan-file">{html.escape(file_name)} · {len(evals)} bookings</span></div>'
            f'<div class="sc-scan-bar"><i></i></div><div class="sc-scan-body">'
            f'<div class="sc-sheet"><div class="sc-sheet-row h"><span>Booking</span><span>Route</span><span>Result</span></div>'
            f'{"".join(rows)}{more}<div class="sc-beam" style="--travel:{travel}px"></div></div>'
            f'<div><div class="sc-steps">{steps}</div><div class="sc-tally">{tally}</div></div></div>'
            f'<div class="sc-skip">Tap anywhere to skip</div></div></div>')

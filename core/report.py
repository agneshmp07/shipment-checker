"""Downloadable HTML booking report (issues, carrier, confirmation). No Streamlit here."""
from __future__ import annotations

from datetime import date
from html import escape

from core import fmt
from core.carriers import label
from core.check import Evaluation
from core.confirmation import DELIVERY_ASSUMPTION
from core.diagnosis import diagnose

COLOURS = {"Blocked": "#c62828", "Warnings": "#ef6c00", "Ready": "#2e7d32", "Red": "#c62828", "Amber": "#ef6c00"}


def html_report(ev: Evaluation) -> str:
    b, rec = ev.booking, ev.recommendation
    e = lambda x: escape(str(x if x is not None else "—"))

    items = "".join(
        f"<tr><td>{e(it.sku)}</td><td>{e(it.description)}</td><td>{e(it.hs_code)}</td>"
        f"<td>{fmt.num(it.quantity)}</td><td>{fmt.money(it.unit_price)}</td><td>{fmt.num(it.units_per_carton)}</td>"
        f"<td>{fmt.num(it.cartons)}</td><td>{fmt.kg(it.unit_weight_kg)}</td><td>{e(it.country_of_origin)}</td></tr>"
        for it in b.items)

    issues = "".join(
        f"<div class='issue' style='border-left-color:{COLOURS[i.severity]}'>"
        f"<b style='color:{COLOURS[i.severity]}'>{i.severity} · {e(i.rule_id)}</b> — <b>{e(i.title)}</b>"
        f"<p>{e(i.explanation)}</p><p><i>Why it matters:</i> {e(i.why_it_matters)}</p>"
        f"<p><i>Fix:</i> {e(i.fix)}</p></div>" for i in ev.issues) or "<p>No issues found. ✅</p>"

    carriers = "".join(
        f"<tr><td>{e(r.status)}</td><td>{e(label(r.option))}</td><td>{fmt.money(r.total_cost)}</td>"
        f"<td>{fmt.num(r.option.transit_days)} days</td><td>{fmt.num(r.option.on_time_rate)}%</td>"
        f"<td>{fmt.kg(r.option.max_weight_per_pallet_kg)}</td><td>{e(r.reason)}</td></tr>"
        for r in rec.all_options)

    roots, _ = diagnose(b, ev.issues)
    root_html = "".join(
        f"<div class='issue' style='border-left-color:#6a1b9a'><b>{e(r.title)}</b> "
        f"<small>({e(r.confidence)} confidence · fixes {len(r.fixes)} issue{'s' if len(r.fixes) != 1 else ''}: "
        f"{e(', '.join(k.rstrip(':') for k in r.fixes))})</small><p>{e(r.explanation)}</p></div>" for r in roots)
    if root_html:
        root_html = "<h2>Most likely root causes</h2>" + root_html

    steps = "".join(f"<li><b>{e(s['step'])}</b> — {e(s['detail'])}</li>" for s in ev.next_steps)

    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>Booking report {e(b.booking_id)}</title>
<style>
body{{font-family:system-ui,Segoe UI,Arial,sans-serif;max-width:900px;margin:24px auto;padding:0 16px;color:#222}}
table{{border-collapse:collapse;width:100%;font-size:14px;margin:8px 0 16px}}
td,th{{border:1px solid #ddd;padding:6px;text-align:left}} th{{background:#f5f5f5}}
.issue{{border-left:5px solid;padding:4px 12px;margin:10px 0;background:#fafafa}} .issue p{{margin:4px 0}}
.badge{{color:#fff;padding:4px 10px;border-radius:12px;background:{COLOURS[ev.status]}}}
</style></head><body>
<h1>Booking {e(b.booking_id)} <span class="badge">{e(ev.badge)}</span></h1>
<p><b>{e(b.seller_name)}</b> · {e(b.route)} · {e(b.destination_type)} · ready {fmt.d(b.ready_date)} ·
priority {e(b.seller_priority)}<br>{fmt.num(b.pallets)} pallets · {fmt.num(b.cartons)} cartons ·
{fmt.money(b.total_declared_value)} declared · {fmt.kg(b.total_gross_weight_kg)} gross ·
delivery appointment {'booked' if b.delivery_appointment_booked else 'not booked'}</p>
<h2>Items</h2><table><tr><th>SKU</th><th>Description</th><th>HS code</th><th>Qty</th><th>Unit price</th>
<th>Units/carton</th><th>Cartons</th><th>Unit weight</th><th>Origin</th></tr>{items}</table>
{root_html}<h2>Checks</h2>{issues}
<h2>Carrier</h2><p>{e(rec.reason)}</p><p>{e(rec.trade_off)}</p>
<table><tr><th>Status</th><th>Carrier</th><th>Total cost</th><th>Transit</th><th>On time</th><th>Max/pallet</th>
<th>Notes</th></tr>{carriers}</table>
<h2>Confirmation</h2><p>{e(ev.summary)}</p><p><small>{e(DELIVERY_ASSUMPTION)}</small></p>
<h2>What happens next</h2><ol>{steps}</ol>
<p><small>Generated {fmt.d(date.today())} by the Shipment pre-flight checker.</small></p>
</body></html>"""

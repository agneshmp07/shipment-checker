"""Printable carton labels: one per carton, "Carton 1 of 90", so the warehouse count matches
what was declared. Eight labels per A4 sheet (2 x 4), each with a Code 39 barcode."""
from __future__ import annotations

from typing import Optional

from fpdf import FPDF
from pydantic import BaseModel

from core import fmt
from core.models import Booking

COLS, ROWS = 2, 4
W, H = 95, 68          # label size in mm
X0, Y0 = 10, 12        # page margins in mm


class Label(BaseModel):
    number: int
    total: int
    sku: str
    description: str
    units: float
    origin: str


def carton_list(b: Booking) -> list[Label]:
    """One entry per carton, numbered across all items. The last carton of an item holds whatever
    is left over when the quantity doesn't divide evenly."""
    plan = []
    for it in b.items:
        cartons = int(it.cartons or 0)
        per = it.units_per_carton or 0
        qty = it.quantity or 0
        for n in range(cartons):
            units = per if n < cartons - 1 else (qty - per * (cartons - 1) if qty and per else per)
            plan.append((it, max(units, 0)))
    total = len(plan)
    return [Label(number=i, total=total, sku=it.sku or "-", description=it.description or "",
                  units=units, origin=it.country_of_origin or "")
            for i, (it, units) in enumerate(plan, 1)]


def _latin(s: str) -> str:
    return (s.replace("—", "-").replace("–", "-").replace("→", "to").replace("’", "'")
            .encode("latin-1", "replace").decode("latin-1"))


def labels_pdf(b: Booking, consignee: Optional[str] = None) -> bytes:
    """consignee: who receives the goods (from the invoice form), else the destination city."""
    labels = carton_list(b)
    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(False)
    navy, orange, grey = (15, 34, 64), (217, 88, 10), (90, 107, 132)
    to_line = consignee or f"{(b.destination_type or 'Receiver').title()} in {b.destination_city or '?'}"
    to_place = f"{b.destination_city or '?'}, {b.destination_country or '?'}"
    from_line = f"{b.seller_name or 'Seller'}, {b.origin_city or '?'}, {b.origin_country or 'United Kingdom'}"
    bid = (b.booking_id or "NEW").upper()

    for i, lab in enumerate(labels):
        if i % (COLS * ROWS) == 0:
            pdf.add_page()
        col, row = i % COLS, (i // COLS) % ROWS
        x, y = X0 + col * W, Y0 + row * H
        pdf.set_draw_color(*grey)
        pdf.set_line_width(0.2)
        pdf.rect(x + 1, y + 1, W - 2, H - 2)                      # cut line

        pdf.set_xy(x + 4, y + 4)
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(*orange)
        pdf.cell(W - 8, 4, _latin(f"BOOKING {bid}"))
        pdf.set_xy(x + 4, y + 9)
        pdf.set_font("Helvetica", "B", 22)
        pdf.set_text_color(*navy)
        pdf.cell(W - 8, 10, f"Carton {lab.number} of {lab.total}")

        pdf.set_font("Helvetica", "", 8.5)
        pdf.set_xy(x + 4, y + 21)
        pdf.cell(W - 8, 4.5, _latin(f"{lab.sku} - {lab.description}"[:58]))
        pdf.set_xy(x + 4, y + 25.5)
        made = f" - made in {lab.origin}" if lab.origin else ""
        pdf.cell(W - 8, 4.5, _latin(f"{fmt.num(lab.units)} units in this carton{made}"))

        pdf.set_font("Helvetica", "B", 8.5)
        pdf.set_xy(x + 4, y + 32)
        pdf.cell(13, 4.5, "TO")
        pdf.set_font("Helvetica", "", 8.5)
        pdf.multi_cell(W - 21, 4.2, _latin(f"{to_line}\n{to_place}"))
        pdf.set_font("Helvetica", "B", 8.5)
        pdf.set_xy(x + 4, y + 42)
        pdf.cell(13, 4.5, "FROM")
        pdf.set_font("Helvetica", "", 8.5)
        pdf.set_xy(x + 17, y + 42)
        pdf.cell(W - 21, 4.5, _latin(from_line[:50]))

        code = f"{bid}-{lab.number:03d}"
        pdf.code39(f"*{code}*", x + 4, y + 49, w=0.3, h=10)
        pdf.set_font("Helvetica", "", 7)
        pdf.set_text_color(*grey)
        pdf.set_xy(x + 4, y + 59.5)
        pdf.cell(W - 8, 3.5, code)
    if not labels:
        pdf.add_page()
        pdf.set_font("Helvetica", "", 12)
        pdf.cell(0, 10, "No cartons to label: add carton counts to the items first.")
    return bytes(pdf.output())

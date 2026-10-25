"""Draft commercial invoice: contents, totals, missing fields, PDF and Excel output."""
import io
from datetime import date

import openpyxl
import pytest

from core.check import evaluate
from core.invoice import TODO, InvoiceDetails, build_invoice, invoice_pdf, invoice_xlsx
from tests.conftest import STANDIN_CARRIERS
from tests.test_rules import booking, item

TODAY = date(2026, 10, 25)
FULL = InvoiceDetails(seller_address="12 Mill Lane, Manchester", seller_contact="sales@example.com",
                      seller_vat_eori="GB123456789000", buyer_name="Haus & Herd GmbH",
                      buyer_address="Hanauer Landstr. 1, Frankfurt", buyer_contact="einkauf@example.de",
                      po_number="PO-778", incoterm="DAP", payment_terms="Bank transfer, 30 days")


def inv_for(b, d=FULL):
    return build_invoice(evaluate(b, STANDIN_CARRIERS, TODAY), d, TODAY)


def test_prefilled_from_booking_and_complete():
    inv = inv_for(booking())
    assert inv.number == "INV-BK-001-20261025" and inv.missing == [] and inv.draft_reason == ""
    (line,) = inv.lines
    assert (line.hs_code, line.origin, line.quantity, line.total, line.net_weight_kg) == \
        ("691200", "United Kingdom", 1080, 5400, 540)
    assert ("Marks", "BK-001 / carton 1 to 90") in inv.packages
    assert ("Incoterms", "DAP Frankfurt (Incoterms 2020)") in inv.references


@pytest.mark.parametrize("term,freight", [("DAP", True), ("CPT", True), ("DDP", True), ("EXW", False), ("FCA", False)])
def test_freight_only_when_seller_pays(term, freight):
    inv = inv_for(booking(), FULL.model_copy(update={"incoterm": term}))
    has = any(label.startswith("Freight") for label, _ in inv.charges)
    assert has is freight
    assert inv.invoice_total == (5400 + 450 if freight else 5400)     # stand-in Test C: 3 × £150


def test_discount_and_insurance():
    inv = inv_for(booking(), FULL.model_copy(update={"incoterm": "EXW", "discount_pct": 10, "insurance_gbp": 25}))
    assert inv.charges == [("Discount 10%", -540.0), ("Insurance", 25.0)]
    assert inv.invoice_total == 5400 - 540 + 25


def test_missing_fields_listed_and_marked():
    inv = inv_for(booking(), InvoiceDetails())
    assert "Buyer name" in inv.missing and "Incoterms agreed with the buyer" in inv.missing
    assert inv.buyer[0] == TODO and len(inv.missing) == 9


def test_draft_when_booking_has_red_issues():
    inv = inv_for(booking([item(hs_code=None)]))
    assert inv.draft_reason.startswith("1 issue must be fixed first: HS code missing")
    assert inv.lines[0].hs_code == "MISSING"


def test_pdf_and_excel_output():
    b = booking([item(description="Mug — blue → glaze")])          # characters core PDF fonts lack
    inv = inv_for(b, InvoiceDetails())
    pdf = invoice_pdf(inv)
    assert pdf.startswith(b"%PDF") and len(pdf) > 1500
    wb = openpyxl.load_workbook(io.BytesIO(invoice_xlsx(inv)))
    ws = wb["Commercial invoice"]
    values = [c.value for row in ws.iter_rows() for c in row if c.value is not None]
    assert "COMMERCIAL INVOICE" in values and "691200" in values and 5400 in values
    assert any(isinstance(v, str) and TODO in v for v in values)

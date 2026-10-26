"""'Commercial invoice' section on a booking's results: short form + PDF / Excel downloads."""
from __future__ import annotations

import streamlit as st

from core.check import Evaluation
from core.invoice import INCOTERMS, PAYMENT_TERMS, InvoiceDetails, build_invoice, invoice_pdf, invoice_xlsx


def render_invoice(ev: Evaluation, key: str):
    b = ev.booking
    store = f"invoice-details-{b.booking_id}"
    d: InvoiceDetails = st.session_state.get(store) or InvoiceDetails()

    st.caption("Customs relies on this document. Oops-Proof fills in everything from your booking — items, "
               "HS codes, origin, values, weights, cartons, route and freight. Add the details only you know.")
    with st.expander("Add buyer, terms and your details", icon=":material/edit_document:",
                     expanded=st.session_state.get(f"{key}-inv-open", False)):
        with st.form(f"{key}-invoice-form", border=False):
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**You (seller)**")
                seller_address = st.text_area("Your address", d.seller_address, height=70)
                seller_contact = st.text_input("Your email or phone", d.seller_contact)
                seller_vat = st.text_input("EORI / VAT number", d.seller_vat_eori,
                                           help="EORI = the number UK customs gives exporters, starting GB. It is "
                                                "also the Exporter Reference Number on the statement on origin.")
                st.markdown("**Terms**")
                p1, p2 = st.columns(2)
                po = p1.text_input("Purchase order or proforma number", d.po_number)
                po_date = p2.text_input("Its date (DD-MM-YYYY)", d.po_date)
                terms = [""] + list(INCOTERMS)
                incoterm = st.selectbox("Incoterms (agreed with the buyer)", terms,
                                        index=terms.index(d.incoterm) if d.incoterm in terms else 0,
                                        format_func=lambda t: "Choose…" if not t else f"{t} — {INCOTERMS[t][0]}",
                                        help="Who pays and is responsible for what. With CPT, CIP, DAP, DPU or DDP "
                                             "you pay the freight, so it's added to the invoice.")
                pay_opts = [""] + PAYMENT_TERMS
                payment = st.selectbox("Payment terms", pay_opts,
                                       index=pay_opts.index(d.payment_terms) if d.payment_terms in pay_opts else 0,
                                       format_func=lambda t: t or "Choose…")
            with c2:
                st.markdown("**Buyer**")
                buyer_name = st.text_input("Buyer name", d.buyer_name)
                buyer_address = st.text_area("Buyer address", d.buyer_address, height=70)
                buyer_contact = st.text_input("Buyer email or phone", d.buyer_contact)
                buyer_vat = st.text_input("Buyer EU VAT / EORI number", d.buyer_vat_eori,
                                          help="The importer's number in the EU, e.g. DE123456789. Their customs "
                                               "declaration needs it.")
                same = st.checkbox("Goods go to the buyer (consignee is the buyer)", d.consignee_same_as_buyer)
                consignee_name = st.text_input("Consignee name, if different", d.consignee_name)
                consignee_address = st.text_area("Consignee address, if different", d.consignee_address, height=70)
                c3, c4 = st.columns(2)
                discount = c3.number_input("Discount %", 0.0, 100.0, d.discount_pct, step=0.5)
                insurance = c4.number_input("Insurance (£)", 0.0, value=d.insurance_gbp, step=10.0)
                c5, c6 = st.columns([2, 1])
                other_label = c5.text_input("Other charges, e.g. certification", d.other_charges_label)
                other = c6.number_input("Amount (£)", 0.0, value=d.other_charges_gbp, step=10.0)
            origin = st.checkbox(
                "Add the UK-EU statement on origin (claims zero tariff in the EU)", d.origin_statement,
                help="Only tick this if the goods meet the UK-EU rules of origin for their HS code. Items not "
                     "made in the UK are listed on the invoice as not covered. Wording: GOV.UK, 'Proving "
                     "originating status… for trade between the UK and EU'.")
            if st.form_submit_button("Update invoice", type="primary", icon=":material/refresh:"):
                st.session_state[store] = InvoiceDetails(
                    seller_address=seller_address, seller_contact=seller_contact, seller_vat_eori=seller_vat,
                    buyer_name=buyer_name, buyer_address=buyer_address, buyer_contact=buyer_contact,
                    consignee_same_as_buyer=same, consignee_name=consignee_name,
                    consignee_address=consignee_address, po_number=po, po_date=po_date, buyer_vat_eori=buyer_vat,
                    incoterm=incoterm, payment_terms=payment, discount_pct=discount, insurance_gbp=insurance,
                    other_charges_label=other_label, other_charges_gbp=other, origin_statement=origin)
                st.session_state[f"{key}-inv-open"] = True
                st.rerun()

    inv = build_invoice(ev, d)
    if d.origin_statement and not inv.origin_statement:
        st.info("None of these items is made in the UK, so the UK-EU statement on origin doesn't apply and "
                "isn't printed.", icon=":material/info:")
    if inv.draft_reason:
        st.warning(f"Draft only — {inv.draft_reason}.", icon=":material/draft:")
    if inv.missing:
        st.caption(f"Still to complete ({len(inv.missing)}): " + ", ".join(inv.missing) +
                   ". They show as TO COMPLETE on the invoice.")
    else:
        st.caption(f"All invoice details are filled in. Total £{inv.invoice_total:,.2f}.")
    with st.container(horizontal=True):
        st.download_button("Invoice (PDF)", lambda: invoice_pdf(inv), file_name=f"{inv.number}.pdf",  # built on click
                           mime="application/pdf", icon=":material/picture_as_pdf:", key=f"{key}-inv-pdf",
                           type="primary")
        st.download_button("Invoice (Excel)", lambda: invoice_xlsx(inv), file_name=f"{inv.number}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           icon=":material/table_view:", key=f"{key}-inv-xlsx")

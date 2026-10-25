"""The "Ask AI" helper available on every page.

It explains; it never decides. Facts about the user's bookings come only from
the Evaluations the rule engine produced, passed in as plain-text context.
Without an LLM, common questions get built-in answers from the same data.
"""
from __future__ import annotations

import re
from typing import Optional

from core import fmt, llm
from core.carriers import label
from core.check import Evaluation
from core.diagnosis import diagnose
from core.rules import RULE_NAMES, TITLES

APP_GUIDE = """ShipCheck helps UK sellers ship goods to Germany, France or the Netherlands.
Pages:
- Home: overview, a one-tap demo, example sentences.
- Book by chat (or voice): describe a shipment in plain English (or tap the mic); the app asks only for
  missing details, confirms calculated values, and you can change anything ("add a pallet").
- Check a file: upload the Bookings + Items Excel sheets (checked as soon as it uploads); a dashboard shows
  Ready / Warnings / Blocked; tap a booking to see each issue with a one-tap fix button.
- Marketplace: directory of buyers and sellers, post your own listing, buyers matched to your bookings,
  messages inbox. Sellers whose bookings all pass get a "Pre-checked shipper" badge.
The 10 rules (Red = must fix before shipping, Amber = warning):
R-01 HS code of at least 6 digits (Red) · R-02 declared value = sum of quantity x unit price within 1% (Red)
· R-03 units per carton x cartons = quantity (Red) · R-04 booking cartons = sum of item cartons (Red)
· R-05 weight per pallet within the chosen carrier's limit (Red) · R-06 no lithium batteries, aerosols or
flammable liquids (Red) · R-07 gross weight >= goods weight (Amber) · R-08 warehouse deliveries need a
booked delivery slot (Amber) · R-09 every item needs a country of origin (Amber) · R-10 ready date not in
the past (Amber).
Carriers: A (economy, cheapest, 5 days, 92% on time, max 500 kg/pallet), B (standard, 3 days, 95%, 750 kg),
C (express, 2 days, 98%, 400 kg). Chosen by the seller's priority: Cheapest, Fastest, Most reliable, Balanced.
Glossary: HS code = international customs code for a product. Pallet = platform holding stacked cartons.
Customs hold = customs stops goods until paperwork is fixed. Delivery appointment = a booked time slot at
the receiving warehouse. Declared value = total value of the goods on the paperwork. Commercial invoice =
the document listing what is shipped, how many and its value; customs relies on it."""

SYSTEM = f"""You are the ShipCheck assistant inside a shipment-booking app. Answer the user's question
in plain English, in at most 120 words, using bullet points only when listing several items.

Rules:
- For anything about the user's bookings, use ONLY the "Current results" context. Quote its real numbers.
- Pass/fail is decided by the app's fixed rules, never by you. Never say a booking passes or fails unless
  the context says so. Never invent bookings, carriers, prices or rules.
- If the user wants to change a booking, tell them how: say it in Book by chat (e.g. "add a pallet") or tap
  the fix button under the issue. You cannot change bookings yourself.
- If the context doesn't contain the answer, say what to do in the app to find it.

About the app:
{APP_GUIDE}"""


# ---- Context -----------------------------------------------------------------------


def describe(ev: Evaluation, detailed: bool = True) -> str:
    b, rec = ev.booking, ev.recommendation
    lines = [f"Booking {b.booking_id} ({b.seller_name or 'seller not set'}): {b.route}, "
             f"{b.destination_type or '?'}, status {ev.badge[2:]}, priority {b.seller_priority or '?'}, "
             f"{fmt.num(b.pallets)} pallets, {fmt.num(b.cartons)} cartons, declared {fmt.money(b.total_declared_value)}, "
             f"gross {fmt.kg(b.total_gross_weight_kg)}, ready {fmt.d(b.ready_date)}."]
    if not detailed:
        if ev.issues:
            lines.append("  Issues: " + "; ".join(f"{i.severity} {i.rule_id} {i.title}" for i in ev.issues))
        return "\n".join(lines)
    items = "; ".join(f"{it.sku} {it.description}: {fmt.num(it.quantity)} units x {fmt.money(it.unit_price)}, "
                      f"{fmt.num(it.units_per_carton)}/carton, {fmt.num(it.cartons)} cartons, HS {it.hs_code or 'none'}, "
                      f"made in {it.country_of_origin or 'not given'}" for it in b.items)
    lines.append(f"  Items: {items or 'none'}")
    for i in ev.issues:
        lines.append(f"  - {i.severity} {i.rule_id} {i.title}: {i.explanation} Fix: {i.fix}")
    if not ev.issues:
        lines.append("  All 10 checks pass.")
    roots, _ = diagnose(b, ev.issues)
    for r in roots:
        lines.append(f"  Root cause ({r.confidence} confidence): {r.title}. {r.explanation}")
    if rec.winner:
        lines.append(f"  Carrier: {rec.reason} {rec.trade_off}")
    else:
        lines.append(f"  Carrier: {rec.reason}")
    lines.append(f"  Confirmation: {ev.summary}")
    return "\n".join(lines)


def build_context(page: str, focus: Optional[Evaluation], chat: Optional[Evaluation],
                  uploads: list[Evaluation], chat_missing: Optional[list[str]] = None) -> str:
    parts = [f"The user is on the {page} page."]
    if chat is not None and chat_missing:
        parts.append("The chat booking is still being filled in, so its status is provisional: say it is "
                     "'not finished yet' rather than 'blocked'. Still needed: " + ", ".join(chat_missing) + ".")
    if focus is not None:
        parts.append("Booking the user is looking at:\n" + describe(focus))
    if chat is not None and (focus is None or chat.booking is not focus.booking):
        parts.append("Chat booking:\n" + describe(chat))
    others = [e for e in uploads if focus is None or e.booking is not focus.booking]
    if others:
        counts = {s: sum(e.status == s for e in uploads) for s in ("Ready", "Warnings", "Blocked")}
        parts.append(f"Uploaded file: {len(uploads)} bookings - {counts['Ready']} ready, "
                     f"{counts['Warnings']} with warnings, {counts['Blocked']} blocked.\n"
                     + "\n".join(describe(e, detailed=False) for e in others[:20]))
    if len(parts) == 1:
        parts.append("The user has no bookings yet.")
    return "\n\n".join(parts)


# ---- Answers -------------------------------------------------------------------------

GLOSSARY = {
    "hs code": "An **HS code** is the international customs code that classifies a product (e.g. 691200 for "
               "ceramic tableware). Customs uses it to set duty, so every item needs at least 6 digits (R-01). "
               "You can look codes up on the UK Trade Tariff (gov.uk/trade-tariff).",
    "pallet": "A **pallet** is the wooden platform your cartons are stacked on. Carriers limit the weight per "
              "pallet: Carrier A 500 kg, B 750 kg, C 400 kg (R-05).",
    "customs hold": "A **customs hold** is when customs stops your goods until a paperwork problem is fixed, "
                    "so stock sits at the border. Wrong HS codes, values, origins and dangerous goods cause it.",
    "declared value": "The **declared value** is the total value of the goods on your paperwork. It must equal "
                      "quantity × unit price across all items, within 1% (R-02).",
    "delivery appointment": "A **delivery appointment** (slot) is a booked time window at the receiving "
                            "warehouse. Warehouses may turn away deliveries without one (R-08).",
    "commercial invoice": "The **commercial invoice** lists what is in the shipment, how many and what it is "
                          "worth. Customs relies on it.",
    "red": ":red-badge[Red] issues must be fixed before the shipment can go; :orange-badge[Amber] issues are "
           "risky and should be fixed or checked.",
}
HOW_TO = {
    "upload": "Go to **Check a file**, tap **Upload** and pick your .xlsx (Bookings + Items sheets). It's "
              "checked as soon as it uploads — scroll down to the results and tap a booking in the table "
              "to see its problems and fixes.",
    "chat": "Go to **Book by chat** and describe your shipment, e.g. *“1080 mugs from Manchester to a "
            "warehouse in Frankfurt”* — or tap the mic and say it. I'll ask only for what's missing.",
    "fix": "Open the booking, find the issue and tap its fix button (e.g. *Set cartons for MUG-01 to 90*). "
           "Every check re-runs instantly and you see the before → after. In the chat you can also just say "
           "the change, like *“add a pallet”*.",
    "marketplace": "Open **Marketplace** to browse buyers and sellers, post your own listing, see buyers "
                   "matched to your bookings and message them.",
}


def offline_answer(question: str, focus: Optional[Evaluation], chat: Optional[Evaluation],
                   uploads: list[Evaluation]) -> str:
    q = question.lower()
    # A specific booking: "why is BK-107 blocked?"
    m = re.search(r"\b(bk-\d+|chat-\d+)\b", q)
    target = None
    pool = ([focus] if focus else []) + ([chat] if chat else []) + uploads
    if m:
        target = next((e for e in pool if (e.booking.booking_id or "").lower() == m.group(1)), None)
        if target is None:
            return f"I can't find booking {m.group(1).upper()} in your current results."
    elif re.search(r"\b(why|block|wrong|problem|issue|fix|status|ready|my booking|this booking)\b", q):
        target = focus or chat
    if target is not None:
        if not target.issues:
            return (f"**{target.booking.booking_id}** passes all 10 checks — {target.badge[2:]}. "
                    f"{target.summary}")
        roots, rest = diagnose(target.booking, target.issues)
        lines = [f"**{target.booking.booking_id}** is **{target.badge[2:]}** because:"]
        for r in roots:
            lines.append(f"- {r.title} ({r.confidence} confidence) — fixes {len(r.fixes)} issue(s).")
        for i in rest:
            lines.append(f"- {i.severity} {i.rule_id} {i.title}: {i.explanation} **Fix:** {i.fix}")
        lines.append("\nTap the fix buttons under each issue to apply a fix and re-check instantly.")
        return "\n".join(lines)
    if re.search(r"carrier|cheapest|fastest|cost|price|delivery date|arrive", q) and (focus or chat):
        ev = focus or chat
        rec = ev.recommendation
        return (f"{rec.reason} {rec.trade_off}".strip() if rec.winner else rec.reason) + \
               (f"\n\n{ev.summary}" if rec.winner else "")
    for key, text in GLOSSARY.items():
        if key in q or (key == "hs code" and re.search(r"\bhs\b", q)):
            return text
    for key, words in (("upload", r"upload|file|excel|xlsx|sheet"), ("chat", r"chat|book|voice|speak|start"),
                       ("fix", r"fix|change|correct|edit"), ("marketplace", r"market|buyer|seller|connect|listing")):
        if re.search(words, q):
            return HOW_TO[key]
    for rid, name in RULE_NAMES.items():
        if rid.lower() in q:
            return f"**{rid} — {name}.** {TITLES[rid]} is what you'll see when it fails. Ask me about a " \
                   "specific booking to see its numbers."
    return ("I can help with: **why a booking is blocked** (e.g. *“why is BK-107 blocked?”*), **how to fix "
            "it**, **carrier choice**, terms like **HS code** or **pallet**, and **how to use each page**.")


def answer(question: str, history: list[dict], page: str, focus: Optional[Evaluation],
           chat: Optional[Evaluation], uploads: list[Evaluation],
           chat_missing: Optional[list[str]] = None) -> tuple[str, str]:
    """Return (answer, source) where source is 'ai' or 'built-in'."""
    if llm.available():
        context = build_context(page, focus, chat, uploads, chat_missing)
        msgs = history[-6:] + [{"role": "user", "content": f"Current results:\n{context}\n\nQuestion: {question}"}]
        try:
            return llm.llm_text(SYSTEM, msgs), "ai"
        except (llm.LLMUnavailable, llm.InvalidOutput):
            pass
    return offline_answer(question, focus, chat, uploads), "built-in"

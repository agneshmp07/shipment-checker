"""Trade Connect (demo): a small directory of businesses, filters, and the
"Pre-checked shipper" badge for sellers whose current bookings all pass."""
from __future__ import annotations

import json
import re
from pathlib import Path

from pydantic import BaseModel

from core.check import Evaluation

DEMO_PATH = Path(__file__).resolve().parent.parent / "data" / "trade_connect_demo.json"


class Business(BaseModel):
    name: str
    country: str
    city: str
    role: str                 # "Buyer" or "Seller"
    categories: list[str]
    about: str


def load_directory(path: Path = DEMO_PATH) -> list[Business]:
    return [Business(**row) for row in json.loads(path.read_text(encoding="utf-8"))]


def filter_directory(entries: list[Business], countries: list[str] | None = None, role: str | None = None,
                     categories: list[str] | None = None, query: str = "") -> list[Business]:
    q = query.strip().lower()
    out = []
    for e in entries:
        if countries and e.country not in countries:
            continue
        if role and role != "All" and e.role != role:
            continue
        if categories and not set(categories) & set(e.categories):
            continue
        if q and q not in " ".join([e.name, e.city, e.country, e.about, *e.categories]).lower():
            continue
        out.append(e)
    return out


def prechecked_sellers(evals: list[Evaluation]) -> dict[str, list[Evaluation]]:
    """Seller name (lower-case) -> their bookings, for sellers whose bookings are ALL 🟢 Ready."""
    by_seller: dict[str, list[Evaluation]] = {}
    for ev in evals:
        if ev.booking.seller_name:
            by_seller.setdefault(ev.booking.seller_name.strip().lower(), []).append(ev)
    return {s: evs for s, evs in by_seller.items() if all(ev.status == "Ready" for ev in evs)}


EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_request(name: str, email: str, message: str) -> list[str]:
    problems = []
    if not name.strip():
        problems.append("Please enter your name.")
    if not EMAIL.match(email.strip()):
        problems.append("Please enter a valid email address.")
    if len(message.strip()) < 10:
        problems.append("Please write a short message (at least 10 characters).")
    return problems


# ---- Matching buyers to a booking ------------------------------------------------------

CATEGORIES = ["Homeware", "Ceramics", "Kitchen", "Apparel", "Accessories", "Textiles", "Stationery",
              "Gifts", "Electronics accessories"]

# word in an item description -> marketplace categories
CATEGORY_WORDS = {
    r"mug|cup|plate|bowl|ceramic|porcelain|pottery|tableware|dinner": ["Ceramics", "Homeware", "Kitchen"],
    r"pan|pot|kitchen|utensil|knife|spoon|tea towel|cookware|frying": ["Kitchen", "Homeware"],
    r"candle|vase|cushion|lamp|frame|decor|home": ["Homeware", "Gifts"],
    r"t-?shirt|shirt|jumper|dress|jacket|hoodie|knit|scarf|sock|clothing|apparel": ["Apparel", "Textiles"],
    r"tote|bag|wallet|belt|hat|cap|accessor": ["Accessories"],
    r"towel|linen|cotton|wool|fabric|textile|blanket": ["Textiles"],
    r"notebook|paper|pen|pencil|card|stationery|diary|planner": ["Stationery", "Gifts"],
    r"gift|toy|book": ["Gifts"],
    r"cable|charger|phone stand|desk organi|usb|stand": ["Electronics accessories"],
}


def categories_for(description: str | None) -> list[str]:
    d = (description or "").lower()
    found: list[str] = []
    for pattern, cats in CATEGORY_WORDS.items():
        if re.search(pattern, d):
            found += [c for c in cats if c not in found]
    return found


class Match(BaseModel):
    business: Business
    score: int
    reasons: list[str]


def match_buyers(booking, directory: list[Business]) -> list[Match]:
    """Buyers who want what this booking ships, best first. A buyer needs a category in common;
    being in the destination country (and city) ranks it higher."""
    goods: dict[str, list[str]] = {}       # category -> item descriptions that map to it
    for it in booking.items:
        for c in categories_for(it.description):
            goods.setdefault(c, []).append(it.description or it.sku or "item")
    matches = []
    for biz in directory:
        if biz.role != "Buyer":
            continue
        shared = [c for c in biz.categories if c in goods]
        if not shared:
            continue
        score, reasons = 2 * len(shared), []
        if biz.country == booking.destination_country:
            score += 3
            where = "in your destination city" if biz.city == booking.destination_city else "in your destination country"
            if biz.city == booking.destination_city:
                score += 2
            reasons.append(f"Based in {biz.city}, {biz.country} — {where}")
        else:
            reasons.append(f"Based in {biz.city}, {biz.country}")
        examples = sorted({d for c in shared for d in goods[c]})[:2]
        reasons.append(f"Buys {', '.join(shared)} — matches your {', '.join(examples)}")
        matches.append(Match(business=biz, score=score, reasons=reasons))
    return sorted(matches, key=lambda m: (-m.score, m.business.name))


# ---- Inbox (demo, in-session) -----------------------------------------------------------------

class Message(BaseModel):
    sender: str          # "you" or the business name
    text: str
    sent: str


class Thread(BaseModel):
    business: str
    messages: list[Message]
    demo_reply_sent: bool = False


def demo_reply(business: Business, first_message: str) -> str:
    """A friendly automatic reply so the inbox feels alive in the demo (clearly labelled in the UI)."""
    wants = ", ".join(business.categories[:2]).lower()
    if business.role == "Buyer":
        return (f"Thanks for reaching out! We're always looking for good {wants} suppliers from the UK. "
                f"Could you send your price list and minimum order quantity? We receive deliveries at our "
                f"{business.city} site.")
    return (f"Hello from {business.name}! Happy to talk. We sell {wants} — what volumes are you looking for, "
            f"and which country should we deliver to?")

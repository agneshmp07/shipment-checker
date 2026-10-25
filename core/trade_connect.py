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

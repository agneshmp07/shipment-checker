"""Single data model shared by chat, file upload, rules, carriers and screens.

Every numeric field is Optional: a booking built in chat is incomplete for a
while, and an uploaded sheet can contain blanks or junk. Missing values are
reported as issues by the loader / rules, never as crashes.
"""
from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field

# ---- Allowed values (from the case brief) ---------------------------------

ORIGIN_COUNTRY = "United Kingdom"
ORIGIN_CITIES = ["London", "Manchester", "Birmingham", "Leeds"]
DESTINATIONS = {
    "Germany": ["Berlin", "Frankfurt", "Hamburg"],
    "France": ["Paris", "Lyon"],
    "Netherlands": ["Amsterdam", "Rotterdam"],
}
DESTINATION_TYPES = ["Warehouse", "Business address"]
PRIORITIES = ["Cheapest", "Fastest", "Most reliable", "Balanced"]
CURRENCIES = ["GBP"]
ITEM_ORIGIN_COUNTRIES = ["United Kingdom", "China", "India", "Vietnam", "Turkey", "Germany"]

Severity = Literal["Red", "Amber"]


class Issue(BaseModel):
    """One problem found on a booking.

    rule_id is "R-01".."R-10" for rulebook checks, or "DATA" for problems in
    the input itself (blank cell, text in a number column, unknown booking ID).
    """
    rule_id: str
    severity: Severity
    title: str
    explanation: str            # what is wrong, with the actual numbers
    why_it_matters: str = ""    # real-world consequence
    fix: str = ""               # specific action
    item_sku: Optional[str] = None
    booking_id: Optional[str] = None
    # Machine-readable fix for the "Apply fix" button (Phase 7), e.g.
    # {"target": "item", "sku": "MUG-01", "field": "cartons", "value": 90}
    fix_action: Optional[dict] = None


class Item(BaseModel):
    booking_id: Optional[str] = None
    sku: Optional[str] = None
    description: Optional[str] = None
    hs_code: Optional[str] = None           # always text; may be blank
    hs_possible_leading_zero_lost: bool = False
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    units_per_carton: Optional[float] = None
    cartons: Optional[float] = None
    unit_weight_kg: Optional[float] = None
    country_of_origin: Optional[str] = None
    source_row: Optional[int] = None        # Excel row, for clearer messages


class Booking(BaseModel):
    booking_id: Optional[str] = None
    seller_name: Optional[str] = None
    origin_city: Optional[str] = None
    origin_country: Optional[str] = ORIGIN_COUNTRY
    destination_city: Optional[str] = None
    destination_country: Optional[str] = None
    destination_type: Optional[str] = None
    ready_date: Optional[date] = None
    seller_priority: Optional[str] = None
    pallets: Optional[float] = None
    cartons: Optional[float] = None
    total_declared_value: Optional[float] = None
    currency: Optional[str] = "GBP"
    total_gross_weight_kg: Optional[float] = None
    delivery_appointment_booked: Optional[bool] = None
    items: list[Item] = Field(default_factory=list)
    # Problems found while reading the input (not rulebook issues)
    data_issues: list[Issue] = Field(default_factory=list)
    source_row: Optional[int] = None

    @property
    def route(self) -> str:
        return f"{self.origin_city or '?'}, {self.origin_country or '?'} → " \
               f"{self.destination_city or '?'}, {self.destination_country or '?'}"


class CarrierOption(BaseModel):
    """One row of Sheet 3 (carrier rate card)."""
    carrier: str
    service: str
    origin_country: str
    destination_country: str
    price_per_pallet: float
    transit_days: float
    on_time_rate: float          # percent, e.g. 92
    max_weight_per_pallet_kg: float


class CarrierResult(BaseModel):
    """A carrier option evaluated for one booking."""
    option: CarrierOption
    status: Literal["Recommended", "Runner-up", "Eligible", "Eliminated"]
    total_cost: Optional[float] = None
    reason: str = ""              # why eliminated, or score breakdown
    score: Optional[float] = None


class Recommendation(BaseModel):
    priority: Optional[str] = None
    winner: Optional[CarrierResult] = None
    runner_up: Optional[CarrierResult] = None
    reason: str = ""
    headline: str = ""          # the choice in one line, e.g. "Carrier A: lowest cost at £540.00 and ..."
    trade_off: str = ""
    all_options: list[CarrierResult] = Field(default_factory=list)
    weight_per_pallet: Optional[float] = None

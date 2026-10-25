"""Display formatting: money as £1,234.00, weights as 620 kg, dates as DD-MM-YYYY."""
from __future__ import annotations

from datetime import date
from typing import Optional


def money(x: Optional[float]) -> str:
    return "—" if x is None else f"£{x:,.2f}"


def num(x: Optional[float]) -> str:
    """1080.0 -> '1,080'; 0.5 -> '0.5'."""
    if x is None:
        return "—"
    if float(x).is_integer():
        return f"{int(x):,}"
    return f"{x:,.2f}".rstrip("0").rstrip(".")


def kg(x: Optional[float]) -> str:
    return "—" if x is None else f"{num(round(x, 1))} kg"


def pct(x: Optional[float]) -> str:
    return "—" if x is None else f"{x:.1f}%"


def d(x: Optional[date]) -> str:
    return "—" if x is None else x.strftime("%d-%m-%Y")

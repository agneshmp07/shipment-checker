"""Build data/carriers.json from Sheet 3 (Carrier options) of the case template.

Usage:  python -m scripts.build_carriers Case2_Shipment_Booking_Test_Data_Format.xlsx

Reads the sheet exactly as given (no invented data), accepts either separate
Carrier / Service and Origin / Destination columns or combined ones
("Carrier A · Road economy", "United Kingdom → Germany"), prints what it
parsed for you to check, and refuses to write if any row is incomplete.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import openpyxl

from core.excel_loader import norm, parse_number
from core.models import CarrierOption

OUT = Path(__file__).resolve().parent.parent / "data" / "carriers.json"

COLUMNS = {   # normalised header -> field
    "carrier": "carrier", "carrier name": "carrier",
    "service": "service", "service level": "service",
    "carrier service": "carrier_service",
    "origin country": "origin_country", "destination country": "destination_country",
    "route": "route", "origin country destination country": "route",
    "price per pallet": "price_per_pallet", "price per pallet gbp": "price_per_pallet",
    "transit time days": "transit_days", "transit time": "transit_days", "transit days": "transit_days",
    "on time rate": "on_time_rate", "on time rate %": "on_time_rate", "on time": "on_time_rate",
    "max weight per pallet kg": "max_weight_per_pallet_kg", "max weight per pallet": "max_weight_per_pallet_kg",
}
SPLIT = re.compile(r"\s*(?:·|→|->|–|—|\s-\s|/)\s*")


def find_sheet(wb):
    for ws in wb.worksheets:
        if "carrier" in norm(ws.title):
            return ws
    return wb.worksheets[2] if len(wb.worksheets) > 2 else None


def parse(path: str) -> tuple[list[CarrierOption], list[str]]:
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = find_sheet(wb)
    if ws is None:
        return [], ["No 'Carrier options' sheet (or third sheet) found."]
    rows = list(ws.iter_rows(values_only=True))
    header_idx = next((i for i, r in enumerate(rows[:15])
                       if any("carrier" in norm(c) for c in r) and any("pallet" in norm(c) for c in r)), None)
    if header_idx is None:
        return [], ["Couldn't find a header row with 'Carrier' and 'pallet' columns."]
    cols = {}
    for j, h in enumerate(rows[header_idx]):
        key = norm(h).replace(" gbp", "").strip()
        if key in COLUMNS:
            cols[j] = COLUMNS[key]
        elif "on time" in key:
            cols[j] = "on_time_rate"
        elif "max weight" in key:
            cols[j] = "max_weight_per_pallet_kg"
        elif "transit" in key:
            cols[j] = "transit_days"
        elif "price" in key and "pallet" in key:
            cols[j] = "price_per_pallet"
    carriers, problems = [], []
    for i in range(header_idx + 1, len(rows)):
        raw = {f: rows[i][j] for j, f in cols.items() if j < len(rows[i])}
        if all(v in (None, "") for v in raw.values()):
            continue
        rec = {}
        if raw.get("carrier_service"):
            parts = SPLIT.split(str(raw["carrier_service"]).strip(), maxsplit=1)
            rec["carrier"], rec["service"] = parts[0], parts[1] if len(parts) > 1 else ""
        if raw.get("route"):
            parts = SPLIT.split(str(raw["route"]).strip(), maxsplit=1)
            rec["origin_country"], rec["destination_country"] = parts[0], parts[1] if len(parts) > 1 else ""
        for f in ("carrier", "service", "origin_country", "destination_country"):
            if raw.get(f) not in (None, ""):
                rec[f] = str(raw[f]).strip()
        rec.setdefault("service", "")
        for f in ("price_per_pallet", "transit_days", "on_time_rate", "max_weight_per_pallet_kg"):
            val, err = parse_number(str(raw.get(f, "")).replace("%", "") if raw.get(f) is not None else None)
            if err:
                problems.append(f"Row {i + 1}: {f} is {err}")
            rec[f] = val
        if rec.get("on_time_rate") is not None and rec["on_time_rate"] <= 1:
            rec["on_time_rate"] *= 100            # 0.92 -> 92
        missing = [f for f in ("carrier", "origin_country", "destination_country") if not rec.get(f)]
        if missing:
            problems.append(f"Row {i + 1}: missing {', '.join(missing)}")
            continue
        if any(rec[f] is None for f in ("price_per_pallet", "transit_days", "on_time_rate", "max_weight_per_pallet_kg")):
            continue
        carriers.append(CarrierOption(**rec))
    if not carriers:
        problems.append("No complete carrier rows found.")
    return carriers, problems


def main(argv: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    if len(argv) != 2:
        print(__doc__)
        return 2
    carriers, problems = parse(argv[1])
    for c in carriers:
        print(f"  {c.carrier:14} {c.service:18} {c.origin_country} → {c.destination_country:12} "
              f"£{c.price_per_pallet:>7.2f}/pallet  {c.transit_days:g} days  {c.on_time_rate:g}% on time  "
              f"max {c.max_weight_per_pallet_kg:g} kg")
    if problems:
        print("\nNOT written — fix these first:\n  " + "\n  ".join(problems))
        return 1
    OUT.write_text(json.dumps([c.model_dump() for c in carriers], indent=2), encoding="utf-8")
    print(f"\nWrote {len(carriers)} carrier options to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

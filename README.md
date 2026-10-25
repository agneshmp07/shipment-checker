# Shipment pre-flight checker

Book a shipment from the UK to Germany, France or the Netherlands — by **chat** or by **uploading
the Bookings + Items sheets** — and catch mistakes before it leaves. Every booking is checked
against the fixed rulebook (R-01 to R-10), each problem is explained with its real numbers, why it
matters and how to fix it, a carrier is recommended for the seller's priority, and a plain-English
confirmation shows what happens next.

## What's in the app

| Page | What it does |
|---|---|
| **Book by chat** | Describe a shipment in your own words. Only missing details are asked for (max 3 at a time); calculated values are confirmed ("That's 90 cartons — correct?"). Change anything mid-conversation ("add a pallet") and get a change summary: `Updated: pallets 3 → 4 · weight per pallet 206.7 kg → 155 kg · cost £450.00 → £600.00 · checks: all passing ✅`. A form is available too. |
| **Upload a file** | Upload an .xlsx with the Bookings and Items sheets (or click *Try the sample file*). Batch dashboard (Ready / Warnings / Blocked, most common problem), then full results per booking. |
| **Results (both)** | Status badge · root causes ("1 root problem → fixes 2 issues", with the most likely wrong number and a confidence level) · every issue with explanation, why it matters, fix · **Apply fix** buttons that re-run all checks and show before → after · recommended carrier with reason and trade-off vs the runner-up · confirmation · next-steps timeline · downloadable HTML report. |
| **Trade Connect** (demo data) | Directory of 14 sample businesses with filters, search and a *Request to connect* form. Sellers whose current bookings are all 🟢 get a **Pre-checked shipper ✅** badge. |

## How decisions are made

- **Rules are plain Python** (`core/rules.py`). The LLM never decides pass/fail.
- **One data model.** Chat and upload both build the same `Booking` (`core/models.py`); everything
  reads from it through one function, `core/check.py::evaluate`.
- **The LLM is optional.** It only (a) extracts fields from chat text into a validated schema,
  (b) phrases follow-up questions, and (c) gives "possible dangerous goods — please confirm" hints.
  Without an API key — or if a call fails — chat uses a built-in rule-based parser
  (`core/offline_parser.py`) and everything else is unaffected.
- **Carrier choice** (`core/carriers.py`): only carriers on the route; those whose max weight per
  pallet is below the booking's weight per pallet are eliminated (with the reason); then ranked by
  priority — Cheapest (tie: higher on-time), Fastest (tie: lower cost), Most reliable (tie: lower
  cost), Balanced = 0.4 × cost + 0.3 × speed + 0.3 × reliability after min-max scaling.
- **Estimated delivery** = ready date + transit days, counted as calendar days.
- **Diagnosis** (`core/diagnosis.py`): for a failed check, each possible typo is tried on a copy
  of the booking and scored by how well it agrees with the other numbers (declared value, carton
  totals, gross weight, typo patterns such as swapped digits or an extra zero).
- **Gross-weight estimate** (R-07 fix): goods weight + 25 kg per empty pallet, shown as a minimum
  with a "re-weigh to confirm" note.

## Run locally

Requires Python 3.11+.

```bash
pip install -r requirements-dev.txt
```

```bash
streamlit run app.py
```

Optional, to switch on the AI assistant: copy `.streamlit/secrets.toml.example` to
`.streamlit/secrets.toml` and fill in `ANTHROPIC_API_KEY` (and optionally `ANTHROPIC_MODEL`,
default `claude-opus-5-5`). Environment variables with the same names work too.

Run the tests (no API key or network needed):

```bash
python -m pytest
```

## ⚠️ Before deploying: load the carrier rate card

`data/carriers.json` must be built from **Sheet 3 (Carrier options)** of the case template. It
is not committed with made-up values — without it the app still runs, but shows a warning, cannot
recommend a carrier, and the pallet-weight check (R-05) cannot run.

```bash
python -m scripts.build_carriers Case2_Shipment_Booking_Test_Data_Format.xlsx
```

The script prints every carrier row it read so you can check it against the sheet, and refuses
to write the file if any row is incomplete. Then run the tests again (they automatically use the
real rate card once it exists).

## Deploy (public link, no login)

### Streamlit Community Cloud
1. Push this folder to a public GitHub repository (`.streamlit/secrets.toml` is git-ignored —
   never commit it).
2. On share.streamlit.io choose **Create app** → your repo → main file `app.py`; under
   *Advanced settings* pick Python 3.11 or later.
3. Optional: paste `ANTHROPIC_API_KEY = "…"` into the app's **Secrets** box.
4. Deploy, then open the link in a private window to confirm it works without signing in.

### Hugging Face Spaces
1. Create a new Space with the **Streamlit** SDK and **Public** visibility.
2. Upload this folder (or push it with git). Add this block at the very top of the Space's
   `README.md` so it starts `app.py`:
   ```yaml
   ---
   title: Shipment pre-flight checker
   sdk: streamlit
   app_file: app.py
   python_version: "3.11"
   ---
   ```
3. Optional: add `ANTHROPIC_API_KEY` under *Settings → Variables and secrets* (as a secret).

## Project layout

```
app.py                     entry point + navigation (st.navigation)
app_pages/                 home, chat_booking, upload_file, trade_connect
ui/results.py              results screen shared by chat and upload
core/models.py             Booking, Item, Issue, CarrierOption, Recommendation
core/excel_loader.py       Sheets 1 & 2 -> list[Booking]; bad input -> issues, never crashes
core/rules.py              R-01 … R-10
core/dangerous_goods.py    R-06 keywords + HS prefixes
core/carriers.py           filtering, ranking, reasons, trade-off
core/confirmation.py       summary, delivery date, next steps
core/check.py              evaluate(): the one pipeline every screen uses
core/diagnosis.py          most likely wrong number, root-cause grouping, apply_fix
core/chat_agent.py         chat engine: merge, missing fields, proposals, change summary
core/llm.py                optional Anthropic calls (structured output)
core/offline_parser.py     no-API fallback for chat
core/report.py             downloadable HTML report
core/trade_connect.py      Trade Connect directory logic
data/carriers.json         rate card from Sheet 3 (build with scripts/build_carriers.py)
data/trade_connect_demo.json  demo businesses
scripts/build_carriers.py  template Sheet 3 -> data/carriers.json
tests/                     pytest suite; tests/fixtures/planted_mistakes.xlsx (+ generator)
```

## Sample file with planted mistakes

`tests/fixtures/planted_mistakes.xlsx` has 14 bookings: 3 clean, each rule broken at least once,
one booking with seven mistakes, one with a junk value, plus an item row for a booking that doesn't
exist. Regenerate it with `python -m tests.fixtures.make_planted_mistakes`; the answer key is in
that script and `tests/test_planted_mistakes.py` checks every booking is flagged with exactly the
expected rules.

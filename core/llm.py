"""Optional LLM helpers (Anthropic API). Nothing here decides pass/fail.

- llm_extract: chat text -> Extraction (structured output, validated by pydantic)
- llm_phrase: rewrite the code-built follow-up question in a friendlier way
- llm_dg_second_opinion: borderline dangerous-goods hints, shown as "please confirm"

Key and model come from ANTHROPIC_API_KEY / ANTHROPIC_MODEL. If the key is
missing or a call fails, callers fall back to deterministic code.
"""
from __future__ import annotations

import json
import os
from datetime import date
from functools import lru_cache
from typing import Optional

import anthropic
from pydantic import BaseModel, ValidationError

from core.chat_agent import ChatState, Extraction
from core.models import DESTINATIONS, DESTINATION_TYPES, ITEM_ORIGIN_COUNTRIES, ORIGIN_CITIES, PRIORITIES

DEFAULT_MODEL = "claude-opus-5-5"
# Models that accept server-side refusal fallbacks ("default" routing).
FALLBACK_MODELS = {"claude-opus-5-5", "claude-opus-5", "claude-fable-5-1", "claude-sonnet-5-5"}


class LLMUnavailable(Exception):
    pass


class InvalidOutput(Exception):
    """The model answered, but not with valid JSON for the schema."""


def model() -> str:
    return os.environ.get("ANTHROPIC_MODEL") or DEFAULT_MODEL


def available() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


@lru_cache(maxsize=1)
def _client(key: str) -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=key, timeout=45.0, max_retries=1)


def _parse(system: str, user: str, schema: type[BaseModel], max_tokens: int = 4000):
    """One structured-output call. Raises LLMUnavailable on any API problem."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise LLMUnavailable("No ANTHROPIC_API_KEY set")
    kwargs = dict(model=model(), max_tokens=max_tokens, system=system,
                  messages=[{"role": "user", "content": user}], output_format=schema,
                  output_config={"effort": "low"})
    try:
        if model() in FALLBACK_MODELS:
            resp = _client(key).beta.messages.parse(betas=["server-side-fallback-2026-07-01"],
                                                    fallbacks="default", **kwargs)
        else:
            resp = _client(key).messages.parse(**kwargs)
    except (ValidationError, ValueError) as e:      # SDK failed to parse/validate the JSON
        raise InvalidOutput(str(e)) from e
    except anthropic.APIError as e:
        raise LLMUnavailable(f"API error: {e}") from e
    if resp.stop_reason in ("refusal", "max_tokens") or resp.parsed_output is None:
        raise InvalidOutput(f"stop_reason={resp.stop_reason}")
    return resp.parsed_output


EXTRACT_SYSTEM = f"""You extract shipment booking details from a seller's chat message.
Return ONLY what the user stated or clearly changed in THIS message; leave every other field null.
Never guess or invent values. Never fill a field just because it is missing.

Allowed values (copy the spelling exactly; if the user names something else, return it as written so code can reject it):
- origin_city: {", ".join(ORIGIN_CITIES)} (origin country is always United Kingdom)
- destination_city: {"; ".join(f"{k}: {', '.join(v)}" for k, v in DESTINATIONS.items())}
- destination_type: {" / ".join(DESTINATION_TYPES)}
- seller_priority: {" / ".join(PRIORITIES)} ("cheap" = Cheapest, "fast/ASAP" = Fastest, "on time" = Most reliable, "no preference" = Balanced)
- country_of_origin (where an item was MADE): {", ".join(ITEM_ORIGIN_COUNTRIES)}
- currency is always GBP; money values are plain numbers.

Rules:
- Relative changes ("add a pallet", "two more cartons", "drop the price to £4"): return the NEW absolute value, computed from the current booking you are given.
- ready_date: DD-MM-YYYY. Resolve "today", "tomorrow", "next Friday" using today's date.
- Items: one ItemPatch per product mentioned. To change an existing item set `match` to its SKU. If only one item exists, changes to "it"/"them" apply to that item (match = its SKU).
- total_gross_weight_kg is the weight of the whole shipment; unit_weight_kg is the weight of ONE unit.
- If we proposed calculated values and the user says yes/correct, set confirms_proposal=true; if they say no, false. Otherwise null.
- If the last question asked whether a delivery slot is booked, a plain yes/no answers delivery_appointment_booked.
- HS code: digits as text, exactly as given."""


def llm_extract(text: str, state: ChatState, today: date) -> Extraction:
    b = state.booking.model_dump(mode="json", exclude={"data_issues", "source_row"})
    for it in b["items"]:
        it.pop("source_row", None)
    pending = [f"{p.target} {p.field} = {p.value} ({p.why})" for p in state.pending]
    last_q = next((m["content"] for m in reversed(state.messages[:-1]) if m["role"] == "assistant"), "")
    user = (f"Today's date: {today.strftime('%d-%m-%Y')}\n"
            f"Current booking (JSON): {json.dumps(b)}\n"
            f"Values we proposed and are waiting for confirmation: {pending or 'none'}\n"
            f"Our last message: {last_q or '(none)'}\n\n"
            f"User message: {text}")
    try:
        return _parse(EXTRACT_SYSTEM, user, Extraction)
    except InvalidOutput:
        try:                                    # retry once on invalid output
            return _parse(EXTRACT_SYSTEM, user, Extraction)
        except InvalidOutput as e:
            raise LLMUnavailable("Model returned invalid JSON twice") from e


class Question(BaseModel):
    text: str


PHRASE_SYSTEM = """You rewrite a shipping assistant's follow-up question so it sounds friendly and natural.
Keep EVERY item it asks for and every number exactly as given (including calculated values awaiting confirmation).
Do not add questions, facts or advice. At most 3 short sentences. Plain English, no lists."""


def llm_phrase(state: ChatState, ask: list, template: str) -> Optional[str]:
    try:
        return _parse(PHRASE_SYSTEM, f"Question to rewrite: {template}", Question, max_tokens=2000).text
    except (LLMUnavailable, InvalidOutput):
        return None


class DGHint(BaseModel):
    sku: str
    reason: str


class DGHints(BaseModel):
    hints: list[DGHint]


DG_SYSTEM = """You review shipment items for POSSIBLE dangerous goods that keyword checks may miss:
lithium batteries (incl. items with built-in batteries), aerosols, flammable liquids or gases.
Only list items with a real, specific reason (e.g. "wireless earbuds contain a lithium battery").
Return an empty list if nothing is likely. Never list an item just because it is unusual."""


def llm_dg_second_opinion(items: list[tuple[str, str]]) -> list[DGHint]:
    """items: [(sku, description)] not already flagged by the keyword/HS check."""
    if not items or not available():
        return []
    listing = "\n".join(f"- {sku}: {desc}" for sku, desc in items)
    try:
        return _parse(DG_SYSTEM, f"Items:\n{listing}", DGHints, max_tokens=2000).hints
    except (LLMUnavailable, InvalidOutput):
        return []

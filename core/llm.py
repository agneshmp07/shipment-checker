"""Optional LLM helpers. Nothing here decides pass/fail.

- llm_extract: chat text -> Extraction (structured output, validated by pydantic)
- llm_phrase: rewrite the code-built follow-up question in a friendlier way
- llm_dg_second_opinion: borderline dangerous-goods hints, shown as "please confirm"

Provider, in order of preference:
  1. Anthropic  - ANTHROPIC_API_KEY (+ optional ANTHROPIC_MODEL)
  2. Gemini     - GEMINI_API_KEY or GOOGLE_API_KEY (+ optional GEMINI_MODEL)
  3. none       - callers fall back to deterministic code (offline parser, templates)
Both providers get the same JSON schema and their replies are validated by the
same pydantic models, so the rest of the app can't tell them apart.
"""
from __future__ import annotations

import copy
import json
import os
from datetime import date
from functools import lru_cache
from typing import Optional

import anthropic
from google import genai
from google.genai import errors as genai_errors
from google.genai import types as genai_types
from pydantic import BaseModel, ValidationError

from core.chat_agent import ChatState, Extraction
from core.models import DESTINATIONS, DESTINATION_TYPES, ITEM_ORIGIN_COUNTRIES, ORIGIN_CITIES, PRIORITIES

DEFAULT_MODEL = "claude-opus-5-5"
# Models that accept server-side refusal fallbacks ("default" routing).
FALLBACK_MODELS = {"claude-opus-5-5", "claude-opus-5", "claude-fable-5-1", "claude-sonnet-5-5"}
GEMINI_DEFAULT_MODEL = "gemini-flash-latest"     # alias that tracks Google's current Flash model
GEMINI_BACKUP_MODEL = "gemini-2.5-flash"          # tried if the configured model isn't found


class LLMUnavailable(Exception):
    pass


class InvalidOutput(Exception):
    """The model answered, but not with valid JSON for the schema."""


def _gemini_key() -> Optional[str]:
    return os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")


def provider() -> Optional[str]:
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    if _gemini_key():
        return "gemini"
    return None


def provider_label() -> str:
    return {"anthropic": f"Claude ({model()})", "gemini": f"Gemini ({model()})"}.get(provider(), "none")


def model() -> str:
    if provider() == "gemini":
        return os.environ.get("GEMINI_MODEL") or GEMINI_DEFAULT_MODEL
    return os.environ.get("ANTHROPIC_MODEL") or DEFAULT_MODEL


def available() -> bool:
    return provider() is not None


@lru_cache(maxsize=1)
def _client(key: str) -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=key, timeout=45.0, max_retries=1)


@lru_cache(maxsize=1)
def _gemini_client(key: str) -> genai.Client:
    return genai.Client(api_key=key, http_options=genai_types.HttpOptions(timeout=45_000))


def _parse(system: str, user: str, schema: type[BaseModel], max_tokens: int = 4000, timeout_s: float = 25):
    """One structured-output call to whichever provider is configured.
    Raises LLMUnavailable on API problems, InvalidOutput on unusable replies."""
    p = provider()
    if p == "anthropic":
        return _parse_anthropic(system, user, schema, max_tokens)
    if p == "gemini":
        return _parse_gemini(system, user, schema, max_tokens, timeout_s)
    raise LLMUnavailable("No API key is configured")


def _parse_anthropic(system: str, user: str, schema: type[BaseModel], max_tokens: int):
    key = os.environ["ANTHROPIC_API_KEY"]
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


def _inline_refs(schema: dict) -> dict:
    """Pydantic puts nested models under $defs; inline them so any JSON-schema reader copes."""
    defs = schema.get("$defs", {})

    def walk(node):
        if isinstance(node, dict):
            if "$ref" in node:
                return walk(copy.deepcopy(defs[node["$ref"].split("/")[-1]]))
            return {k: walk(v) for k, v in node.items() if k != "$defs"}
        if isinstance(node, list):
            return [walk(v) for v in node]
        return node
    return walk(schema)


# Thinking slows every reply; this app only extracts fields, so ask for as little as the
# model allows. Gemini 3 takes thinking_level, Gemini 2.5 takes thinking_budget; whichever
# the model accepts first is remembered per model.
_THINKING_MODES = [
    genai_types.ThinkingConfig(thinking_level=genai_types.ThinkingLevel.MINIMAL),
    genai_types.ThinkingConfig(thinking_budget=0),
    None,
]
_thinking_mode_for: dict[str, int] = {}


def _gemini_generate(m: str, system: str, contents, extra: dict, max_tokens: int, timeout_s: float):
    first = _thinking_mode_for.get(m, 0)
    for idx in range(first, len(_THINKING_MODES)):
        config = genai_types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=max(max_tokens, 8192),        # thinking models count reasoning here too
            thinking_config=_THINKING_MODES[idx],
            http_options=genai_types.HttpOptions(timeout=int(timeout_s * 1000)),
            **extra)
        try:
            resp = _gemini_client(_gemini_key()).models.generate_content(model=m, contents=contents, config=config)
            _thinking_mode_for[m] = idx
            return resp
        except genai_errors.ClientError as e:
            if e.code == 400 and idx < len(_THINKING_MODES) - 1:
                continue                                    # this thinking setting isn't supported
            raise


def _gemini_call(system: str, contents, extra: dict, max_tokens: int, timeout_s: float) -> str:
    """Call the configured Gemini model (backup model if it isn't found); return the reply text."""
    primary = os.environ.get("GEMINI_MODEL") or GEMINI_DEFAULT_MODEL
    models = [primary] + ([GEMINI_BACKUP_MODEL] if primary != GEMINI_BACKUP_MODEL else [])
    resp = None
    for i, m in enumerate(models):
        try:
            resp = _gemini_generate(m, system, contents, extra, max_tokens, timeout_s)
            break
        except genai_errors.ClientError as e:
            if e.code == 404 and i < len(models) - 1:
                continue                             # model name not available: try the backup
            raise LLMUnavailable(f"Gemini error {e.code}: {e.message}") from e
        except genai_errors.APIError as e:
            raise LLMUnavailable(f"Gemini error {e.code}: {e.message}") from e
        except Exception as e:                       # network / timeout
            raise LLMUnavailable(f"Gemini unavailable: {type(e).__name__}") from e
    text = getattr(resp, "text", None)
    if not text:
        raise InvalidOutput("Gemini returned no text")
    return text


def _parse_gemini(system: str, user: str, schema: type[BaseModel], max_tokens: int, timeout_s: float = 25):
    text = _gemini_call(system, user, {"response_mime_type": "application/json",
                                       "response_json_schema": _inline_refs(schema.model_json_schema())},
                        max_tokens, timeout_s)
    try:
        return schema.model_validate_json(text)
    except ValidationError as e:
        raise InvalidOutput(str(e)) from e


def llm_text(system: str, messages: list[dict], max_tokens: int = 1500, timeout_s: float = 25) -> str:
    """Plain-text reply to a conversation [{"role": "user"|"assistant", "content": str}].
    Raises LLMUnavailable / InvalidOutput like _parse."""
    p = provider()
    if p == "anthropic":
        key = os.environ["ANTHROPIC_API_KEY"]
        kwargs = dict(model=model(), max_tokens=max_tokens, system=system, messages=messages,
                      output_config={"effort": "low"})
        try:
            if model() in FALLBACK_MODELS:
                resp = _client(key).beta.messages.create(betas=["server-side-fallback-2026-07-01"],
                                                         fallbacks="default", **kwargs)
            else:
                resp = _client(key).messages.create(**kwargs)
        except anthropic.APIError as e:
            raise LLMUnavailable(f"API error: {e}") from e
        if resp.stop_reason == "refusal":
            raise InvalidOutput("refused")
        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip()
        if not text:
            raise InvalidOutput("empty reply")
        return text
    if p == "gemini":
        contents = [{"role": "model" if m["role"] == "assistant" else "user", "parts": [{"text": m["content"]}]}
                    for m in messages]
        return _gemini_call(system, contents, {}, max_tokens, timeout_s).strip()
    raise LLMUnavailable("No API key is configured")


# ---- Voice (Gemini only: Claude has no speech input/output) ---------------------------

GEMINI_TTS_MODEL = "gemini-2.5-flash-preview-tts"
TTS_VOICE = "Kore"            # a clear, neutral prebuilt voice


def voice_available() -> bool:
    return bool(_gemini_key())


def transcribe(audio: bytes, mime_type: str = "audio/wav") -> str:
    """Speech to text for a short voice message."""
    if not _gemini_key():
        raise LLMUnavailable("Voice needs a Gemini key")
    part = genai_types.Part.from_bytes(data=audio, mime_type=mime_type)
    text = _gemini_call(
        "You transcribe short voice messages from sellers booking shipments. Return only the words spoken, "
        "in English, with numbers written as digits (e.g. 1080, £5, 0.5 kg). No commentary. If there is no "
        "speech, return an empty string.",
        [part, "Transcribe this voice message."], {}, 1000, 30)
    return text.strip().strip('"')


def _wav(pcm: bytes, rate: int = 24000) -> bytes:
    """Wrap raw 16-bit mono PCM (what Gemini TTS returns) in a WAV header."""
    import io
    import wave
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)
    return buf.getvalue()


def speak(text: str) -> Optional[bytes]:
    """Text to speech as WAV bytes, or None if unavailable (callers then use the browser's voice)."""
    if not _gemini_key() or not text.strip():
        return None
    config = genai_types.GenerateContentConfig(
        response_modalities=["AUDIO"],
        speech_config=genai_types.SpeechConfig(voice_config=genai_types.VoiceConfig(
            prebuilt_voice_config=genai_types.PrebuiltVoiceConfig(voice_name=TTS_VOICE))),
        http_options=genai_types.HttpOptions(timeout=20_000))
    try:
        resp = _gemini_client(_gemini_key()).models.generate_content(
            model=os.environ.get("GEMINI_TTS_MODEL") or GEMINI_TTS_MODEL,
            contents=f"Say in a friendly, clear British voice: {text}", config=config)
        blob = resp.candidates[0].content.parts[0].inline_data
    except Exception:                       # any API, quota or shape problem: fall back quietly
        return None
    if blob is None or not blob.data:
        return None
    if "wav" in (blob.mime_type or ""):
        return blob.data
    rate = 24000
    if blob.mime_type and "rate=" in blob.mime_type:
        try:
            rate = int(blob.mime_type.split("rate=")[1].split(";")[0])
        except ValueError:
            pass
    return _wav(blob.data, rate)


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
        # Nice-to-have only: if it isn't quick, the code-built question is used instead.
        return _parse(PHRASE_SYSTEM, f"Question to rewrite: {template}", Question, max_tokens=2000,
                      timeout_s=8).text
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

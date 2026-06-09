"""Shared parsing helpers for market names, prices and variants."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from urllib.parse import unquote, urlparse

STEAM_CURRENCY_CODES = {
    "1": "USD",
    "3": "EUR",
    "5": "GBP",
}
QUALITY_PATTERN = re.compile(
    r"\((Factory New|Minimal Wear|Field-Tested|Well-Worn|Battle-Scarred)\)\s*$",
    re.IGNORECASE,
)


def parse_market_decimal(value: str) -> Decimal | None:
    match = re.search(r"\d[\d.,]*(?:[,.]--)?", value)
    if match is None:
        return None
    cleaned = match.group(0).replace(" ", "")
    cleaned = re.sub(r"([,.])--$", r"\g<1>00", cleaned)
    cleaned = cleaned.rstrip(".,-")
    if "," in cleaned and "." in cleaned:
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif "," in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def parse_required_market_decimal(value: str) -> Decimal:
    parsed = parse_market_decimal(value)
    if parsed is None:
        raise ValueError(f"could not parse decimal from {value!r}")
    return parsed


def parse_int_from_text(value: object) -> int | None:
    if value is None:
        return None
    digits = re.sub(r"[^0-9]", "", str(value))
    return int(digits) if digits else None


def detect_currency(value: str, *, default: str | None = None) -> str | None:
    lowered = value.lower()
    if "eur" in lowered or "\u20ac" in value:
        return "EUR"
    if "\u00a5" in value or "cny" in lowered:
        return "CNY"
    if "$" in value or "usd" in lowered:
        return "USD"
    if "\u00a3" in value or "gbp" in lowered:
        return "GBP"
    if "pln" in lowered or "z\u0142" in lowered:
        return "PLN"
    return default


def steam_currency_code(price_text: str, configured_currency: str) -> str:
    detected = detect_currency(price_text)
    if detected is not None:
        return detected
    return STEAM_CURRENCY_CODES.get(configured_currency, "EUR")


def parse_market_hash_from_steam_url(url: str | None) -> str | None:
    if not url:
        return None
    path = urlparse(url).path
    parts = path.split("/market/listings/730/")
    if len(parts) != 2:
        return None
    return unquote(parts[1])


def parse_item_text(value: str) -> tuple[str, str | None, bool]:
    text = clean_text(value)
    stattrak = "stattrak" in text.lower()
    match = QUALITY_PATTERN.search(text)
    quality = match.group(1) if match else None
    if quality:
        text = QUALITY_PATTERN.sub("", text).strip()
    return text, quality, stattrak


def asset_name_from_market_hash(value: str) -> str:
    name, _quality, _stattrak = parse_item_text(value)
    return name


def quality_from_market_hash(value: str) -> str | None:
    _name, quality, _stattrak = parse_item_text(value)
    return quality


def market_hash_name(item_name: str, quality: str | None) -> str:
    return f"{item_name} ({quality})" if quality else item_name


def variant_key(quality: str | None, stattrak: bool) -> str:
    quality_key = (quality or "default").strip().lower().replace(" ", "_")
    return f"{quality_key}_st{int(stattrak)}"


def clean_text(value: object) -> str:
    return " ".join(str(value or "").split()).strip()

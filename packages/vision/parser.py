"""Parse OCR text into normalized market observations."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from packages.contracts.observations import MarketObservationContract
from packages.domain.canonical_id import build_canonical_asset_id
from packages.domain.enums import SourceType
from packages.domain.market_parsing import parse_market_decimal, variant_key

PRICE_PATTERN = re.compile(
    r"(?P<amount>\d[\d.,]*(?:[,.]--)?)(?:\s*)"
    r"(?P<currency>EUR|USD|GBP|\u20ac|\$|\u00a3)?"
)
QUALITY_PATTERN = re.compile(
    r"\((Factory New|Minimal Wear|Field-Tested|Well-Worn|Battle-Scarred)\)",
    re.IGNORECASE,
)
PLATFORMS = {
    "steam": "steam",
    "steam market": "steam",
    "buff": "buff",
}


class OCRParseError(ValueError):
    """Raised when OCR text cannot be parsed into valid observations."""


@dataclass(frozen=True, slots=True)
class OCRObservationRecord:
    observation: MarketObservationContract
    asset_name: str
    category: str | None = None
    quality: str | None = None
    variant_key: str = "default"
    confidence: float = 0.0


def parse_ocr_market_observations(
    text: str,
    *,
    observed_at: datetime | None = None,
    correlation_id: str = "ocr:manual",
    default_platform_id: str = "ocr",
    default_currency: str = "EUR",
    confidence: float = 1.0,
    min_confidence: float = 0.5,
    source_reference: str | None = None,
) -> tuple[OCRObservationRecord, ...]:
    if confidence < min_confidence:
        return ()

    timestamp = observed_at or datetime.now(tz=UTC)
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        timestamp = timestamp.replace(tzinfo=UTC)

    records: list[OCRObservationRecord] = []
    for line_number, raw_line in enumerate(_candidate_lines(text), start=1):
        parsed = _parse_line(raw_line, default_platform_id, default_currency)
        if parsed is None:
            continue
        asset_name, quality, stattrak, platform_id, price, currency, volume = parsed
        observation = MarketObservationContract(
            correlation_id=correlation_id,
            asset_id=build_canonical_asset_id(
                name=asset_name,
                quality=quality,
                stattrak=stattrak,
            ),
            platform_id=platform_id,
            observed_at=timestamp,
            price=price,
            currency=currency,
            source_type=SourceType.OCR,
            volume=volume,
            source_reference=source_reference,
            raw_payload={
                "line_number": line_number,
                "text": raw_line,
                "ocr_confidence": confidence,
            },
        )
        records.append(
            OCRObservationRecord(
                observation=observation,
                asset_name=asset_name,
                quality=quality,
                variant_key=variant_key(quality, stattrak),
                confidence=confidence,
            )
        )
    return tuple(records)


def _candidate_lines(text: str) -> tuple[str, ...]:
    normalized = _normalize_text(text)
    lines = [line.strip(" |-;") for line in normalized.splitlines()]
    if len(lines) <= 1 and normalized:
        lines = [normalized]
    return tuple(line for line in lines if line)


def _parse_line(
    line: str,
    default_platform_id: str,
    default_currency: str,
) -> tuple[str, str | None, bool, str, Decimal, str, int | None] | None:
    price_match = _last_price_match(line)
    if price_match is None:
        return None
    price = parse_market_decimal(price_match.group("amount"))
    if price is None or price <= 0 or price > Decimal("1000000"):
        return None

    before_price = line[: price_match.start()].strip(" |-;:")
    if not before_price:
        return None

    asset_name = _strip_platform(before_price)
    quality = _parse_quality(asset_name)
    stattrak = "stattrak" in asset_name.lower()
    asset_name = QUALITY_PATTERN.sub("", asset_name).strip(" |-;")
    if not asset_name:
        return None
    return (
        asset_name,
        quality,
        stattrak,
        _detect_platform(before_price) or default_platform_id,
        price,
        _normalize_currency(price_match.group("currency"), default_currency),
        _parse_volume(line[price_match.end() :]),
    )


def _last_price_match(line: str) -> re.Match[str] | None:
    matches = [
        match
        for match in PRICE_PATTERN.finditer(line)
        if match.group("currency") or _looks_like_price(match.group("amount"))
    ]
    return matches[-1] if matches else None


def _looks_like_price(value: str) -> bool:
    return "." in value or "," in value


def _normalize_currency(value: str | None, default_currency: str) -> str:
    if value is None:
        return default_currency.upper()
    if value == "\u20ac":
        return "EUR"
    if value == "$":
        return "USD"
    if value == "\u00a3":
        return "GBP"
    return value.upper()


def _detect_platform(text: str) -> str | None:
    lowered = text.lower()
    for token, platform_id in PLATFORMS.items():
        if token in lowered:
            return platform_id
    return None


def _strip_platform(text: str) -> str:
    parts = [part.strip() for part in re.split(r"\s+[|-]\s+|\s{2,}", text) if part.strip()]
    if len(parts) > 1 and _detect_platform(parts[-1]):
        return " | ".join(parts[:-1])
    return text.strip()


def _parse_quality(text: str) -> str | None:
    match = QUALITY_PATTERN.search(text)
    return match.group(1) if match else None


def _parse_volume(text: str) -> int | None:
    match = re.search(r"(?:vol(?:ume)?|x)\D*(\d+)", text, flags=re.IGNORECASE)
    return int(match.group(1)) if match else None


def _normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text)
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
    normalized = re.sub(r"[ \t]+", " ", normalized)
    return normalized.strip()

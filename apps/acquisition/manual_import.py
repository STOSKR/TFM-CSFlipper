"""Manual CSV/JSON market observation import."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from packages.contracts.observations import MarketObservationContract
from packages.domain.canonical_id import build_canonical_asset_id
from packages.domain.enums import SourceType


class ManualImportError(ValueError):
    """Raised when a manual import file cannot be normalized."""


@dataclass(frozen=True, slots=True)
class ManualObservationRecord:
    observation: MarketObservationContract
    asset_name: str
    category: str | None = None
    quality: str | None = None
    variant_key: str = "default"


def load_manual_observations(path: str | Path) -> tuple[ManualObservationRecord, ...]:
    file_path = Path(path)
    if file_path.suffix.lower() == ".csv":
        return _load_csv(file_path)
    if file_path.suffix.lower() == ".json":
        return _load_json(file_path)
    raise ManualImportError(f"unsupported import format: {file_path.suffix}")


def _load_csv(path: Path) -> tuple[ManualObservationRecord, ...]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        return tuple(
            _record_from_flat_row(row, row_number=index, source_reference=str(path))
            for index, row in enumerate(reader, start=2)
        )


def _load_json(path: Path) -> tuple[ManualObservationRecord, ...]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return tuple(
            _record_from_flat_row(row, row_number=index, source_reference=str(path))
            for index, row in enumerate(payload, start=1)
            if isinstance(row, dict)
        )
    if isinstance(payload, dict) and isinstance(payload.get("variants"), dict):
        return _records_from_grouped_price_json(payload, source_reference=str(path))
    raise ManualImportError("json import must be a list of rows or grouped price JSON")


def _record_from_flat_row(
    row: dict[str, Any],
    *,
    row_number: int,
    source_reference: str,
) -> ManualObservationRecord:
    try:
        asset_name = _required_text(row, "asset_name", "item_name", "name")
        quality = _optional_text(row, "quality", "wear")
        stattrak = _parse_bool(row.get("stattrak", row.get("st", False)))
        asset_id = _optional_text(
            row,
            "asset_id",
            "canonical_asset_id",
        ) or build_canonical_asset_id(name=asset_name, quality=quality, stattrak=stattrak)
        platform_id = _optional_text(row, "platform_id", "platform", "source") or "manual"
        observed_at = _parse_datetime(_required_text(row, "observed_at", "timestamp", "t"))
        price = _parse_decimal(_required_text(row, "price", "p"))
        currency = _optional_text(row, "currency", "ccy") or "EUR"
        source_type_raw = _optional_text(row, "source_type") or SourceType.CSV.value
        volume = _parse_optional_int(row.get("volume", row.get("vol")))
        variant_key = _optional_text(row, "variant_key") or _variant_key(quality, stattrak)
    except (KeyError, TypeError, ValueError) as exc:
        raise ManualImportError(f"invalid row {row_number}: {exc}") from exc

    observation = MarketObservationContract(
        correlation_id=_optional_text(row, "correlation_id") or f"manual:{source_reference}",
        asset_id=asset_id,
        platform_id=platform_id,
        observed_at=observed_at,
        price=price,
        currency=currency,
        source_type=SourceType(source_type_raw),
        volume=volume,
        source_reference=_optional_text(row, "source_reference") or source_reference,
        raw_payload=dict(row),
    )
    return ManualObservationRecord(
        observation=observation,
        asset_name=asset_name,
        category=_optional_text(row, "category"),
        quality=quality,
        variant_key=variant_key,
    )


def _records_from_grouped_price_json(
    payload: dict[str, Any],
    *,
    source_reference: str,
) -> tuple[ManualObservationRecord, ...]:
    item_key = str(payload.get("item_key") or payload.get("name") or "").strip()
    if not item_key:
        raise ManualImportError("grouped JSON must include item_key")

    records: list[ManualObservationRecord] = []
    variants = payload["variants"]
    for variant_name, variant_payload in variants.items():
        if not isinstance(variant_payload, dict):
            continue
        quality = str(variant_payload.get("w") or variant_name).split("_", 1)[0].upper()
        stattrak = _parse_bool(variant_payload.get("st", "st1" in str(variant_name).lower()))
        series = variant_payload.get("series")
        if not isinstance(series, list):
            continue
        asset_id = build_canonical_asset_id(name=item_key, quality=quality, stattrak=stattrak)
        variant_key = _variant_key(quality, stattrak)
        for index, row in enumerate(series, start=1):
            if not isinstance(row, dict):
                continue
            try:
                observed_at = datetime.fromtimestamp(int(row["t"]), tz=UTC)
                price = (Decimal(str(row["p"])) / Decimal("100")).quantize(Decimal("0.01"))
                volume = _parse_optional_int(row.get("vol"))
                currency = str(row.get("ccy") or variant_payload.get("ccy") or "EUR").upper()
            except (KeyError, TypeError, ValueError) as exc:
                raise ManualImportError(f"invalid grouped JSON row {variant_name}:{index}") from exc
            observation = MarketObservationContract(
                correlation_id=f"manual:{source_reference}",
                asset_id=asset_id,
                platform_id="steam",
                observed_at=observed_at,
                price=price,
                currency=currency,
                source_type=SourceType.CSV,
                volume=volume,
                source_reference=f"{source_reference}:{variant_name}",
                raw_payload=dict(row),
            )
            records.append(
                ManualObservationRecord(
                    observation=observation,
                    asset_name=item_key,
                    quality=quality,
                    variant_key=variant_key,
                )
            )
    return tuple(records)


def _required_text(row: dict[str, Any], *names: str) -> str:
    value = _optional_text(row, *names)
    if value is None:
        raise KeyError(f"missing required field: {'/'.join(names)}")
    return value


def _optional_text(row: dict[str, Any], *names: str) -> str | None:
    for name in names:
        value = row.get(name)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _parse_datetime(value: str) -> datetime:
    if value.isdigit():
        return datetime.fromtimestamp(int(value), tz=UTC)
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def _parse_decimal(value: str) -> Decimal:
    normalized = value.replace(",", ".")
    return Decimal(normalized)


def _parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "stattrak"}


def _parse_optional_int(value: Any) -> int | None:
    if value is None or str(value).strip() == "":
        return None
    return int(value)


def _variant_key(quality: str | None, stattrak: bool) -> str:
    quality_key = (quality or "default").strip().lower().replace(" ", "_")
    return f"{quality_key}_st{int(stattrak)}"

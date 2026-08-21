"""Durable local Parquet archive for normalized market-history observations."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pandas as pd  # type: ignore[import-untyped]
import pyarrow as pa
import pyarrow.parquet as pq

from packages.persistence.simple_market import SimpleMarketSnapshot, history_points_from_snapshot


@dataclass(frozen=True, slots=True)
class HistoryArchiveWriteReport:
    rows: int
    files: tuple[Path, ...]
    backup_files: tuple[Path, ...]


def default_history_backup_dir() -> Path | None:
    """Return the configured external sync folder without requiring it to exist."""

    configured = os.getenv("HISTORY_ARCHIVE_BACKUP_DIR") or os.getenv("OneDrive")
    if not configured:
        return None
    return Path(configured) / "CSFlipper-history" / "market_history_v1"


def write_snapshot_history_archive(
    snapshots: Sequence[SimpleMarketSnapshot],
    *,
    archive_dir: Path,
    backup_dir: Path | None = None,
    cny_per_eur: Decimal = Decimal("8"),
) -> HistoryArchiveWriteReport:
    """Archive all normalized points from a refresh before any retention is applied."""

    if cny_per_eur <= 0:
        raise ValueError("cny_per_eur must be positive")
    records = [
        _snapshot_point_record(snapshot, point, cny_per_eur=cny_per_eur)
        for snapshot in snapshots
        for point in history_points_from_snapshot(snapshot)
    ]
    return write_history_archive_records(records, archive_dir=archive_dir, backup_dir=backup_dir)


def write_history_archive_records(
    records: Sequence[Mapping[str, Any]],
    *,
    archive_dir: Path,
    backup_dir: Path | None = None,
) -> HistoryArchiveWriteReport:
    """Write content-addressed Parquet parts, optionally mirrored to a second directory."""

    partitions: dict[tuple[int, int], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        normalized = _normalize_record(record)
        observed_at = datetime.fromisoformat(normalized["observed_at"].replace("Z", "+00:00"))
        partitions[(observed_at.year, observed_at.month)].append(normalized)

    files: list[Path] = []
    backup_files: list[Path] = []
    for (year, month), rows in sorted(partitions.items()):
        relative_dir = Path(f"year={year:04d}") / f"month={month:02d}"
        digest = _rows_digest(rows)
        target = archive_dir / relative_dir / f"part-{digest}.parquet"
        _write_parquet_part(target, rows)
        files.append(target)
        if backup_dir is not None:
            backup = backup_dir / relative_dir / target.name
            _copy_verified(target, backup)
            backup_files.append(backup)

    return HistoryArchiveWriteReport(
        rows=sum(len(rows) for rows in partitions.values()),
        files=tuple(files),
        backup_files=tuple(backup_files),
    )


def load_history_archive(archive_dir: Path) -> pd.DataFrame:
    """Load the archive into the normalized frame expected by dataset builders."""

    files = sorted(path for path in archive_dir.rglob("*.parquet") if path.is_file())
    if not files:
        raise FileNotFoundError(f"no Parquet history files found in {archive_dir}")
    frames = [pd.read_parquet(path) for path in files]
    return pd.concat(frames, ignore_index=True)


def _snapshot_point_record(
    snapshot: SimpleMarketSnapshot,
    point: Mapping[str, Any],
    *,
    cny_per_eur: Decimal,
) -> dict[str, Any]:
    metric_name = str(point["metric_name"])
    metric_value = Decimal(str(point["metric_value"]))
    currency = _text_or_none(point.get("currency"))
    price_eur, price_cny = _normalized_prices(
        metric_name=metric_name,
        metric_value=metric_value,
        currency=currency,
        cny_per_eur=cny_per_eur,
    )
    return {
        "item_id": snapshot.representation_name,
        "representation_name": snapshot.representation_name,
        "name": snapshot.name,
        "quality": snapshot.quality,
        "stattrak": snapshot.stattrak,
        "observed_at": point["observed_at"],
        "platform_id": point["platform_id"],
        "metric_name": metric_name,
        "metric_value": metric_value,
        "currency": currency,
        "price_eur": price_eur,
        "price_cny": price_cny,
        "raw_payload": point.get("raw_payload") or {},
        "archived_at": snapshot.scraped_at,
        "archive_source": "local_refresh",
    }


def _normalize_record(record: Mapping[str, Any]) -> dict[str, Any]:
    observed_at = _utc_text(record.get("observed_at"))
    archived_at = _utc_text(record.get("archived_at") or record.get("observed_at"))
    return {
        "item_id": str(record["item_id"]),
        "representation_name": str(record["representation_name"]),
        "name": str(record["name"]),
        "quality": str(record["quality"]),
        "stattrak": bool(record["stattrak"]),
        "observed_at": observed_at,
        "platform_id": str(record["platform_id"]),
        "metric_name": str(record["metric_name"]),
        "metric_value": float(record["metric_value"]),
        "currency": _text_or_none(record.get("currency")),
        "price_eur": _float_or_none(record.get("price_eur")),
        "price_cny": _float_or_none(record.get("price_cny")),
        "raw_payload": json.dumps(record.get("raw_payload") or {}, sort_keys=True, default=str),
        "archived_at": archived_at,
        "archive_source": str(record.get("archive_source") or "unknown"),
    }


def _normalized_prices(
    *,
    metric_name: str,
    metric_value: Decimal,
    currency: str | None,
    cny_per_eur: Decimal,
) -> tuple[Decimal | None, Decimal | None]:
    if metric_name not in {"sell_price", "buy_order_price"} or currency is None:
        return None, None
    if currency == "EUR":
        return metric_value, metric_value * cny_per_eur
    if currency == "CNY":
        return metric_value / cny_per_eur, metric_value
    return None, None


def _write_parquet_part(target: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        return
    temporary = target.with_suffix(".tmp")
    table = pa.Table.from_pylist(list(rows))
    pq.write_table(table, temporary, compression="zstd")  # type: ignore[no-untyped-call]
    temporary.replace(target)


def _copy_verified(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        temporary = target.with_suffix(".tmp")
        shutil.copy2(source, temporary)
        temporary.replace(target)
    if _file_digest(source) != _file_digest(target):
        raise OSError(f"archive backup checksum mismatch: {target}")


def _rows_digest(rows: Sequence[Mapping[str, Any]]) -> str:
    payload = json.dumps(list(rows), sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(payload).hexdigest()[:20]


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _utc_text(value: object) -> str:
    if isinstance(value, datetime):
        current = value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)
        return current.isoformat()
    text = str(value).strip()
    if not text:
        raise ValueError("archive history point requires observed_at")
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    current = parsed.astimezone(UTC) if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    return current.isoformat()


def _text_or_none(value: object) -> str | None:
    text = str(value or "").strip().upper()
    return text or None


def _float_or_none(value: object) -> float | None:
    if value is None:
        return None
    return float(str(value))

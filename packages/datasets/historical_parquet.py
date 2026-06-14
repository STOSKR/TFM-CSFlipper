"""Import helpers for historical CS2 price parquet datasets."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from packages.persistence.simple_market import SimpleMarketSnapshot

REQUIRED_COLUMNS = frozenset(
    {
        "variant_id",
        "weapon_key",
        "skin_key",
        "w",
        "st",
        "sales",
        "price_cents",
    }
)
DATE_COLUMNS = ("ds", "day", "observed_at")
QUALITY_BY_CODE = {
    "FN": "Factory New",
    "MW": "Minimal Wear",
    "FT": "Field-Tested",
    "WW": "Well-Worn",
    "BS": "Battle-Scarred",
}
WEAPON_DISPLAY = {
    "ak47": "AK-47",
    "ak_47": "AK-47",
    "aug": "AUG",
    "awp": "AWP",
    "cz75a": "CZ75-Auto",
    "cz75_auto": "CZ75-Auto",
    "deagle": "Desert Eagle",
    "desert_eagle": "Desert Eagle",
    "famas": "FAMAS",
    "g3sg1": "G3SG1",
    "galilar": "Galil AR",
    "galil_ar": "Galil AR",
    "m249": "M249",
    "m4a1s": "M4A1-S",
    "m4a1_s": "M4A1-S",
    "m4a4": "M4A4",
    "mac10": "MAC-10",
    "mac_10": "MAC-10",
    "mp5sd": "MP5-SD",
    "mp5_sd": "MP5-SD",
    "mp7": "MP7",
    "mp9": "MP9",
    "negev": "Negev",
    "p250": "P250",
    "p90": "P90",
    "r8": "R8 Revolver",
    "r8_revolver": "R8 Revolver",
    "scar20": "SCAR-20",
    "scar_20": "SCAR-20",
    "sg553": "SG 553",
    "sg_553": "SG 553",
    "ssg08": "SSG 08",
    "ssg_08": "SSG 08",
    "ump45": "UMP-45",
    "ump_45": "UMP-45",
    "usp_s": "USP-S",
    "usps": "USP-S",
    "xm1014": "XM1014",
}


@dataclass(frozen=True, slots=True)
class ParquetImportReport:
    path: Path
    rows: int
    variants: int
    date_column: str
    min_observed_at: datetime | None
    max_observed_at: datetime | None
    missing_columns: tuple[str, ...] = ()

    @property
    def valid(self) -> bool:
        return not self.missing_columns


def inspect_direction_parquet(path: Path) -> ParquetImportReport:
    table = _read_parquet_table(path)
    columns = set(table.column_names)
    missing = tuple(sorted(REQUIRED_COLUMNS - columns))
    date_column = _date_column(columns)
    if date_column is None:
        missing = tuple(sorted((*missing, "one of ds/day/observed_at")))
        return ParquetImportReport(
            path=path,
            rows=table.num_rows,
            variants=0,
            date_column="",
            min_observed_at=None,
            max_observed_at=None,
            missing_columns=missing,
        )

    rows = _table_rows(table, columns=[date_column, "variant_id"])
    observed_values = [_parse_datetime(row[date_column]) for row in rows]
    observed = [value for value in observed_values if value is not None]
    variants = len({str(row["variant_id"]) for row in rows})
    return ParquetImportReport(
        path=path,
        rows=table.num_rows,
        variants=variants,
        date_column=date_column,
        min_observed_at=min(observed) if observed else None,
        max_observed_at=max(observed) if observed else None,
        missing_columns=missing,
    )


def snapshots_from_direction_parquet(
    path: Path,
    *,
    currency: str = "EUR",
    limit_variants: int | None = None,
) -> tuple[SimpleMarketSnapshot, ...]:
    report = inspect_direction_parquet(path)
    if not report.valid:
        raise ValueError(f"missing required parquet columns: {', '.join(report.missing_columns)}")

    table = _read_parquet_table(path)
    rows = _table_rows(table)
    rows_by_variant: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        variant_id = str(row["variant_id"])
        if limit_variants is not None and variant_id not in rows_by_variant:
            if len(rows_by_variant) >= limit_variants:
                continue
        rows_by_variant.setdefault(variant_id, []).append(row)

    snapshots = [
        _snapshot_from_rows(variant_rows, currency=currency, date_column=report.date_column)
        for variant_rows in rows_by_variant.values()
        if variant_rows
    ]
    return tuple(snapshot for snapshot in snapshots if snapshot is not None)


def _snapshot_from_rows(
    rows: list[dict[str, Any]],
    *,
    currency: str,
    date_column: str,
) -> SimpleMarketSnapshot | None:
    ordered = sorted(
        rows,
        key=lambda row: _parse_datetime(row[date_column]) or datetime.min.replace(tzinfo=UTC),
    )
    latest = ordered[-1]
    observed_at = _parse_datetime(latest[date_column])
    if observed_at is None:
        return None

    history_rows: list[dict[str, Any]] = []
    for row in ordered:
        row_observed_at = _parse_datetime(row[date_column])
        if row_observed_at is None:
            continue
        history_rows.append(
            {
                "source": "direction_dataset_model_sample",
                "observed_at": row_observed_at.isoformat(),
                "price": str(_price_from_cents(row["price_cents"])),
                "sales_count": _optional_int(row.get("sales")),
                "variant_id": str(row["variant_id"]),
                "future_return": _optional_float(row.get("future_return")),
                "direction": _optional_str(row.get("direction")),
                "is_up": _optional_int(row.get("is_up")),
            }
        )

    return SimpleMarketSnapshot(
        name=_item_name(latest),
        quality=_quality(str(latest["w"])),
        stattrak=bool(_optional_int(latest.get("st")) or 0),
        scraped_at=observed_at,
        steam_price=_price_from_cents(latest["price_cents"]),
        steam_currency=currency,
        steam_recent_sales=tuple(history_rows),
    )


def _read_parquet_table(path: Path) -> Any:
    try:
        import pyarrow.parquet as parquet
    except ModuleNotFoundError as exc:  # pragma: no cover - dependency guard
        raise RuntimeError("pyarrow is required to import parquet history files") from exc
    return parquet.read_table(path)  # type: ignore[no-untyped-call]


def _table_rows(table: Any, *, columns: list[str] | None = None) -> list[dict[str, Any]]:
    selected = table.select(columns) if columns is not None else table
    return [dict(row) for row in selected.to_pylist()]


def _date_column(columns: set[str]) -> str | None:
    for column in DATE_COLUMNS:
        if column in columns:
            return column
    return None


def _parse_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


def _item_name(row: dict[str, Any]) -> str:
    weapon = _weapon_display(str(row["weapon_key"]))
    skin = _title_from_key(str(row["skin_key"]))
    return f"{weapon} | {skin}"


def _weapon_display(value: str) -> str:
    key = value.strip().lower().replace("-", "_")
    return WEAPON_DISPLAY.get(key, _title_from_key(key))


def _title_from_key(value: str) -> str:
    return " ".join(
        token.upper() if len(token) <= 3 else token.title()
        for token in value.split("_")
    )


def _quality(value: str) -> str:
    text = value.strip()
    return QUALITY_BY_CODE.get(text.upper(), text)


def _price_from_cents(value: object) -> Decimal:
    return (Decimal(str(value)) / Decimal("100")).quantize(Decimal("0.01"))


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(str(value))
    except ValueError:
        return None


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value))
    except ValueError:
        return None


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None

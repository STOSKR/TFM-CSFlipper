"""Build versioned supervised datasets from engineered historical parquet files."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

DATE_COLUMN = "ds"
TARGET_COLUMN = "is_up"
DEFAULT_VALIDATION_START = datetime(2025, 1, 1)
DEFAULT_TEST_START = datetime(2026, 1, 1)
DEFAULT_BATCH_SIZE = 65_536

TRACE_COLUMNS = (
    "variant_id",
    "item_key",
    "unique_id",
    "ds",
)
LEAKAGE_COLUMNS = frozenset(
    {
        "future_price_cents",
        "future_return",
        "direction",
        "is_safe",
        "is_up",
        "y",
        "y_7d_direction",
    }
)
NON_FEATURE_COLUMNS = frozenset((*TRACE_COLUMNS, "day"))
DERIVED_CATEGORICAL_FEATURES = (
    "primary_item_key",
    "weapon_wear_key",
    "skin_wear_key",
    "collection_rarity_key",
    "rarity_wear_key",
)
DERIVED_NUMERIC_FEATURES = (
    "price_eur",
    "log_variant_age_days",
    "low_liquidity",
    "turnover_eur",
    "log_turnover_eur",
    "sales_per_price_eur",
    "ret_1d_clipped",
    "ret_3d_clipped",
    "ret_7d_clipped",
    "ret_14d_clipped",
    "ret_30d_clipped",
    "price_vs_ma_7d_clipped",
    "price_vs_ma_14d_clipped",
    "price_vs_ma_30d_clipped",
    "sales_z_7d_clipped",
    "sales_z_14d_clipped",
    "sales_z_30d_clipped",
)
DERIVED_FEATURE_TYPES = {
    **{name: pa.string() for name in DERIVED_CATEGORICAL_FEATURES},
    **{name: pa.float64() for name in DERIVED_NUMERIC_FEATURES},
}


@dataclass(frozen=True, slots=True)
class SupervisedDatasetBuildConfig:
    input_path: Path
    output_dir: Path
    start_date: datetime | None = None
    validation_start: datetime = DEFAULT_VALIDATION_START
    test_start: datetime = DEFAULT_TEST_START
    target_column: str = TARGET_COLUMN
    date_column: str = DATE_COLUMN
    batch_size: int = DEFAULT_BATCH_SIZE
    profile_max_categories: int = 10_000


def build_supervised_dataset(config: SupervisedDatasetBuildConfig) -> dict[str, Any]:
    parquet_file = pq.ParquetFile(config.input_path)  # type: ignore[no-untyped-call]
    source_columns = tuple(parquet_file.schema_arrow.names)
    _validate_columns(source_columns, config)

    source_feature_columns = supervised_feature_columns(parquet_file.schema_arrow, config=config)
    derived_feature_columns = derived_supervised_feature_columns(source_columns)
    feature_columns = (*source_feature_columns, *derived_feature_columns)
    output_columns = _ordered_existing_columns(
        source_columns,
        (*TRACE_COLUMNS, *source_feature_columns, config.target_column),
    )
    output_columns = (*output_columns, *derived_feature_columns)
    output_schema = _schema_for_columns(parquet_file.schema_arrow, output_columns)
    numeric_features = tuple(
        name
        for name in feature_columns
        if (
            name in DERIVED_NUMERIC_FEATURES
            or (
                name not in DERIVED_CATEGORICAL_FEATURES
                and _is_numeric(parquet_file.schema_arrow.field(name).type)
            )
        )
    )
    categorical_features = tuple(name for name in feature_columns if name not in numeric_features)

    config.output_dir.mkdir(parents=True, exist_ok=True)
    split_paths = {
        "train": config.output_dir / "train.parquet",
        "validation": config.output_dir / "validation.parquet",
        "test": config.output_dir / "test.parquet",
    }
    writers: dict[str, pq.ParquetWriter | None] = {name: None for name in split_paths}
    split_stats = {name: _empty_split_stats() for name in split_paths}
    rows_included = 0
    profiler = _FeatureProfiler(
        numeric_features=numeric_features,
        categorical_features=categorical_features,
        target_column=config.target_column,
        max_categories=config.profile_max_categories,
    )

    try:
        for batch in parquet_file.iter_batches(  # type: ignore[no-untyped-call]
            batch_size=config.batch_size,
            columns=output_columns,
        ):
            table = pa.Table.from_batches([batch])
            table = _filter_start_table(table, config=config)
            if table.num_rows == 0:
                continue
            table = _append_derived_features(table, derived_feature_columns)
            rows_included += table.num_rows
            profiler.observe(table)
            for split_name, split_table in _split_table(table, config=config).items():
                if split_table.num_rows == 0:
                    continue
                split_stats[split_name] = _merge_split_stats(
                    split_stats[split_name],
                    split_table,
                    date_column=config.date_column,
                    target_column=config.target_column,
                )
                if writers[split_name] is None:
                    writers[split_name] = pq.ParquetWriter(
                        split_paths[split_name],
                        output_schema,
                    )  # type: ignore[no-untyped-call]
                writer = writers[split_name]
                if writer is not None:
                    writer.write_table(split_table.select(output_columns))  # type: ignore[no-untyped-call]
    finally:
        for writer in writers.values():
            if writer is not None:
                writer.close()  # type: ignore[no-untyped-call]

    for split_name, writer in writers.items():
        if writer is None:
            pq.write_table(  # type: ignore[no-untyped-call]
                pa.Table.from_batches([], schema=output_schema),
                split_paths[split_name],
            )

    metadata = {
        "schema_version": "supervised_direction_dataset.v1",
        "source_path": str(config.input_path),
        "source_rows": parquet_file.metadata.num_rows,
        "rows_included": rows_included,
        "output_dir": str(config.output_dir),
        "created_at": datetime.now(tz=UTC).isoformat(),
        "date_column": config.date_column,
        "target_column": config.target_column,
        "target_semantics": "1 when future directional return is up, 0 otherwise",
        "split_policy": {
            "start": (
                f"{config.date_column} >= {config.start_date.date().isoformat()}"
                if config.start_date is not None
                else None
            ),
            "train": f"{config.date_column} < {config.validation_start.date().isoformat()}",
            "validation": (
                f"{config.validation_start.date().isoformat()} <= {config.date_column} "
                f"< {config.test_start.date().isoformat()}"
            ),
            "test": f"{config.date_column} >= {config.test_start.date().isoformat()}",
        },
        "splits": split_stats,
        "trace_columns": list(_ordered_existing_columns(source_columns, TRACE_COLUMNS)),
        "feature_columns": list(feature_columns),
        "numeric_features": list(numeric_features),
        "categorical_features": list(categorical_features),
        "primary_group_column": (
            "primary_item_key" if "primary_item_key" in derived_feature_columns else None
        ),
        "excluded_columns": sorted(LEAKAGE_COLUMNS | NON_FEATURE_COLUMNS),
        "source_columns": list(source_columns),
    }
    feature_profile = profiler.profile(total_rows=rows_included)

    _write_json(config.output_dir / "metadata.json", metadata)
    _write_json(config.output_dir / "feature_profile.json", feature_profile)
    return metadata


def supervised_feature_columns(
    schema: pa.Schema,
    *,
    config: SupervisedDatasetBuildConfig | None = None,
) -> tuple[str, ...]:
    active_config = config or SupervisedDatasetBuildConfig(
        input_path=Path("-"),
        output_dir=Path("-"),
    )
    excluded = LEAKAGE_COLUMNS | NON_FEATURE_COLUMNS | {active_config.target_column}
    return tuple(name for name in schema.names if name not in excluded)


def derived_supervised_feature_columns(source_columns: tuple[str, ...]) -> tuple[str, ...]:
    columns = set(source_columns)
    derived: list[str] = []
    if {"item_key", "w", "st"} <= columns:
        derived.append("primary_item_key")
    if {"weapon_key", "w"} <= columns:
        derived.append("weapon_wear_key")
    if {"skin_key", "w"} <= columns:
        derived.append("skin_wear_key")
    if {"collection", "rarity"} <= columns:
        derived.append("collection_rarity_key")
    if {"rarity", "w"} <= columns:
        derived.append("rarity_wear_key")
    if "price_cents" in columns:
        derived.append("price_eur")
    if "variant_age_days" in columns:
        derived.append("log_variant_age_days")
    if "sales" in columns:
        derived.append("low_liquidity")
    if {"price_cents", "sales"} <= columns:
        derived.extend(("turnover_eur", "log_turnover_eur", "sales_per_price_eur"))
    for name in ("ret_1d", "ret_3d", "ret_7d", "ret_14d", "ret_30d"):
        if name in columns:
            derived.append(f"{name}_clipped")
    for name in ("price_vs_ma_7d", "price_vs_ma_14d", "price_vs_ma_30d"):
        if name in columns:
            derived.append(f"{name}_clipped")
    for name in ("sales_z_7d", "sales_z_14d", "sales_z_30d"):
        if name in columns:
            derived.append(f"{name}_clipped")
    return tuple(derived)


def _validate_columns(
    source_columns: tuple[str, ...],
    config: SupervisedDatasetBuildConfig,
) -> None:
    missing = [
        column
        for column in (config.date_column, config.target_column)
        if column not in source_columns
    ]
    if missing:
        raise ValueError(f"missing required dataset columns: {', '.join(missing)}")
    if config.validation_start >= config.test_start:
        raise ValueError("validation_start must be before test_start")
    if config.start_date is not None and config.start_date >= config.validation_start:
        raise ValueError("start_date must be before validation_start")
    if config.batch_size <= 0:
        raise ValueError("batch_size must be positive")


def _ordered_existing_columns(
    source_columns: tuple[str, ...],
    requested_columns: tuple[str, ...],
) -> tuple[str, ...]:
    requested = set(requested_columns)
    return tuple(name for name in source_columns if name in requested)


def _schema_for_columns(schema: pa.Schema, columns: tuple[str, ...]) -> pa.Schema:
    fields = [
        schema.field(name) if name in schema.names else pa.field(name, DERIVED_FEATURE_TYPES[name])
        for name in columns
    ]
    return pa.schema(fields)


def _append_derived_features(
    table: pa.Table,
    derived_columns: tuple[str, ...],
) -> pa.Table:
    if not derived_columns:
        return table
    result = table
    for name in derived_columns:
        result = result.append_column(name, _derived_array(table, name))
    return result


def _derived_array(table: pa.Table, name: str) -> pa.Array:
    if name == "primary_item_key":
        return _string_key(table, ("item_key", "w", "st"))
    if name == "weapon_wear_key":
        return _string_key(table, ("weapon_key", "w"))
    if name == "skin_wear_key":
        return _string_key(table, ("skin_key", "w"))
    if name == "collection_rarity_key":
        return _string_key(table, ("collection", "rarity"))
    if name == "rarity_wear_key":
        return _string_key(table, ("rarity", "w"))
    if name == "price_eur":
        return _float_array(_numeric_values(table, "price_cents") / 100.0)
    if name == "log_variant_age_days":
        return _float_array(np.log1p(np.maximum(_numeric_values(table, "variant_age_days"), 0.0)))
    if name == "low_liquidity":
        return _float_array((_numeric_values(table, "sales") < 10.0).astype(float))
    if name == "turnover_eur":
        turnover = (_numeric_values(table, "price_cents") / 100.0) * _numeric_values(
            table,
            "sales",
        )
        return _float_array(turnover)
    if name == "log_turnover_eur":
        turnover = (_numeric_values(table, "price_cents") / 100.0) * _numeric_values(table, "sales")
        return _float_array(np.log1p(np.maximum(turnover, 0.0)))
    if name == "sales_per_price_eur":
        price_eur = _numeric_values(table, "price_cents") / 100.0
        return _float_array(
            _safe_divide(_numeric_values(table, "sales"), np.maximum(price_eur, 0.01))
        )
    if name.endswith("_clipped"):
        source = name.removesuffix("_clipped")
        if source.startswith("sales_z_"):
            return _float_array(np.clip(_numeric_values(table, source), -5.0, 5.0))
        return _float_array(np.clip(_numeric_values(table, source), -1.0, 3.0))
    raise ValueError(f"unknown derived feature: {name}")


def _string_key(table: pa.Table, columns: tuple[str, ...]) -> pa.Array:
    values = [_string_values(table, column) for column in columns]
    combined = values[0]
    for value in values[1:]:
        combined = np.char.add(np.char.add(combined, "__"), value)
    return pa.array(combined.tolist(), type=pa.string())


def _string_values(table: pa.Table, column: str) -> np.ndarray[Any, np.dtype[np.str_]]:
    series = table[column].to_pandas().astype("string").fillna("unknown")
    return np.asarray(series.astype(str), dtype=np.str_)


def _numeric_values(table: pa.Table, column: str) -> np.ndarray[Any, np.dtype[np.float64]]:
    return np.asarray(table[column].to_pandas(), dtype=np.float64)


def _float_array(values: np.ndarray[Any, np.dtype[np.float64]]) -> pa.Array:
    return pa.array(values, type=pa.float64())


def _safe_divide(
    numerator: np.ndarray[Any, np.dtype[np.float64]],
    denominator: np.ndarray[Any, np.dtype[np.float64]],
) -> np.ndarray[Any, np.dtype[np.float64]]:
    result = np.divide(
        numerator,
        denominator,
        out=np.zeros_like(numerator, dtype=np.float64),
        where=denominator != 0,
    )
    return cast(np.ndarray[Any, np.dtype[np.float64]], result)


def _split_table(
    table: pa.Table,
    *,
    config: SupervisedDatasetBuildConfig,
) -> dict[str, pa.Table]:
    dates = table[config.date_column]
    validation_start = pa.scalar(config.validation_start, type=dates.type)
    test_start = pa.scalar(config.test_start, type=dates.type)
    train_mask = pc.less(dates, validation_start)  # type: ignore[attr-defined]
    validation_mask = pc.and_(  # type: ignore[attr-defined]
        pc.greater_equal(dates, validation_start),  # type: ignore[attr-defined]
        pc.less(dates, test_start),  # type: ignore[attr-defined]
    )
    test_mask = pc.greater_equal(dates, test_start)  # type: ignore[attr-defined]
    return {
        "train": table.filter(train_mask),
        "validation": table.filter(validation_mask),
        "test": table.filter(test_mask),
    }


def _filter_start_table(
    table: pa.Table,
    *,
    config: SupervisedDatasetBuildConfig,
) -> pa.Table:
    if config.start_date is None:
        return table
    dates = table[config.date_column]
    start = pa.scalar(config.start_date, type=dates.type)
    return table.filter(pc.greater_equal(dates, start))  # type: ignore[attr-defined]


def _empty_split_stats() -> dict[str, Any]:
    return {
        "rows": 0,
        "target_positive": 0,
        "target_negative": 0,
        "target_nulls": 0,
        "target_rate": None,
        "min_date": None,
        "max_date": None,
    }


def _merge_split_stats(
    current: dict[str, Any],
    table: pa.Table,
    *,
    date_column: str,
    target_column: str,
) -> dict[str, Any]:
    rows = table.num_rows
    target = table[target_column]
    target_valid = pc.drop_null(target)  # type: ignore[attr-defined]
    target_positive = int(_scalar_value(pc.sum(target_valid)) or 0)  # type: ignore[attr-defined]
    target_nulls = int(
        _scalar_value(pc.sum(pc.is_null(target))) or 0  # type: ignore[attr-defined]
    )
    target_negative = rows - target_positive - target_nulls
    min_date = _datetime_scalar(pc.min(table[date_column]))  # type: ignore[attr-defined]
    max_date = _datetime_scalar(pc.max(table[date_column]))  # type: ignore[attr-defined]

    merged = dict(current)
    merged["rows"] += rows
    merged["target_positive"] += target_positive
    merged["target_negative"] += target_negative
    merged["target_nulls"] += target_nulls
    merged["min_date"] = _min_iso(merged["min_date"], min_date)
    merged["max_date"] = _max_iso(merged["max_date"], max_date)
    valid_targets = merged["target_positive"] + merged["target_negative"]
    merged["target_rate"] = (
        merged["target_positive"] / valid_targets if valid_targets else None
    )
    return merged


class _FeatureProfiler:
    def __init__(
        self,
        *,
        numeric_features: tuple[str, ...],
        categorical_features: tuple[str, ...],
        target_column: str,
        max_categories: int,
    ) -> None:
        self._numeric_features = numeric_features
        self._categorical_features = categorical_features
        self._target_column = target_column
        self._max_categories = max_categories
        self._numeric = {name: _empty_numeric_stats() for name in numeric_features}
        self._categorical = {name: _empty_categorical_stats() for name in categorical_features}

    def observe(self, table: pa.Table) -> None:
        target = _numeric_array(table[self._target_column])
        target_valid = np.isfinite(target)
        for name in self._numeric_features:
            values = _numeric_array(table[name])
            stats = self._numeric[name]
            valid = np.isfinite(values) & target_valid
            stats["rows"] += int(len(values))
            stats["nulls"] += int(len(values) - np.count_nonzero(np.isfinite(values)))
            if not np.any(valid):
                continue
            valid_values = values[valid]
            valid_target = target[valid]
            stats["count"] += int(len(valid_values))
            stats["sum_x"] += float(np.sum(valid_values))
            stats["sum_x2"] += float(np.sum(valid_values * valid_values))
            stats["sum_y"] += float(np.sum(valid_target))
            stats["sum_y2"] += float(np.sum(valid_target * valid_target))
            stats["sum_xy"] += float(np.sum(valid_values * valid_target))
            stats["min"] = _min_float(stats["min"], float(np.min(valid_values)))
            stats["max"] = _max_float(stats["max"], float(np.max(valid_values)))
            positive = valid_target >= 0.5
            if np.any(positive):
                stats["positive_count"] += int(np.count_nonzero(positive))
                stats["positive_sum"] += float(np.sum(valid_values[positive]))
            negative = ~positive
            if np.any(negative):
                stats["negative_count"] += int(np.count_nonzero(negative))
                stats["negative_sum"] += float(np.sum(valid_values[negative]))

        for name in self._categorical_features:
            stats = self._categorical[name]
            values = table[name].to_pylist()
            stats["rows"] += len(values)
            for value in values:
                if value is None:
                    stats["nulls"] += 1
                    continue
                if len(stats["values"]) < self._max_categories:
                    stats["values"].add(str(value))
                else:
                    stats["truncated"] = True

    def profile(self, *, total_rows: int) -> dict[str, Any]:
        numeric = [
            _finalize_numeric_profile(name, stats)
            for name, stats in self._numeric.items()
        ]
        numeric.sort(
            key=lambda item: abs(float(item["target_correlation"] or 0.0)),
            reverse=True,
        )
        categorical = [
            {
                "feature": name,
                "rows": stats["rows"],
                "null_fraction": _safe_fraction(stats["nulls"], stats["rows"]),
                "distinct_count_capped": len(stats["values"]),
                "distinct_values_truncated": stats["truncated"],
            }
            for name, stats in self._categorical.items()
        ]
        categorical.sort(key=lambda item: int(item["distinct_count_capped"]), reverse=True)
        return {
            "schema_version": "feature_profile.v1",
            "rows_observed": total_rows,
            "numeric_features_ranked": numeric,
            "categorical_features": categorical,
        }


def _empty_numeric_stats() -> dict[str, Any]:
    return {
        "rows": 0,
        "nulls": 0,
        "count": 0,
        "sum_x": 0.0,
        "sum_x2": 0.0,
        "sum_y": 0.0,
        "sum_y2": 0.0,
        "sum_xy": 0.0,
        "min": None,
        "max": None,
        "positive_count": 0,
        "positive_sum": 0.0,
        "negative_count": 0,
        "negative_sum": 0.0,
    }


def _empty_categorical_stats() -> dict[str, Any]:
    return {
        "rows": 0,
        "nulls": 0,
        "values": set(),
        "truncated": False,
    }


def _finalize_numeric_profile(name: str, stats: dict[str, Any]) -> dict[str, Any]:
    count = int(stats["count"])
    correlation = None
    if count > 1:
        numerator = count * stats["sum_xy"] - stats["sum_x"] * stats["sum_y"]
        x_variance = count * stats["sum_x2"] - stats["sum_x"] ** 2
        y_variance = count * stats["sum_y2"] - stats["sum_y"] ** 2
        denominator = math.sqrt(max(x_variance, 0.0) * max(y_variance, 0.0))
        if denominator > 0:
            correlation = numerator / denominator

    positive_mean = _safe_fraction(stats["positive_sum"], stats["positive_count"])
    negative_mean = _safe_fraction(stats["negative_sum"], stats["negative_count"])
    return {
        "feature": name,
        "rows": stats["rows"],
        "valid_pairs": count,
        "null_fraction": _safe_fraction(stats["nulls"], stats["rows"]),
        "min": stats["min"],
        "max": stats["max"],
        "target_correlation": correlation,
        "positive_mean": positive_mean,
        "negative_mean": negative_mean,
        "positive_negative_mean_delta": (
            positive_mean - negative_mean
            if positive_mean is not None and negative_mean is not None
            else None
        ),
    }


def _numeric_array(array: Any) -> np.ndarray[Any, np.dtype[np.float64]]:
    values = array.to_pandas()
    return np.asarray(values, dtype=np.float64)


def _scalar_value(value: Any) -> Any:
    return value.as_py() if hasattr(value, "as_py") else value


def _datetime_scalar(value: Any) -> datetime | None:
    raw = _scalar_value(value)
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw
    return datetime.fromisoformat(str(raw))


def _min_iso(current: str | None, candidate: datetime | None) -> str | None:
    if candidate is None:
        return current
    candidate_iso = candidate.isoformat()
    return candidate_iso if current is None or candidate_iso < current else current


def _max_iso(current: str | None, candidate: datetime | None) -> str | None:
    if candidate is None:
        return current
    candidate_iso = candidate.isoformat()
    return candidate_iso if current is None or candidate_iso > current else current


def _min_float(current: float | None, candidate: float) -> float:
    return candidate if current is None else min(current, candidate)


def _max_float(current: float | None, candidate: float) -> float:
    return candidate if current is None else max(current, candidate)


def _safe_fraction(numerator: float | int, denominator: float | int) -> float | None:
    if denominator == 0:
        return None
    return float(numerator) / float(denominator)


def _is_numeric(data_type: pa.DataType) -> bool:
    return bool(
        pa.types.is_integer(data_type)
        or pa.types.is_floating(data_type)
        or pa.types.is_decimal(data_type)
    )


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(_jsonable(payload), indent=2, sort_keys=True), encoding="utf-8")


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, set):
        return sorted(str(item) for item in value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value

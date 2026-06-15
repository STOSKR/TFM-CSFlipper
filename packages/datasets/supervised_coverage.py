"""Coverage diagnostics for supervised train/validation/test parquet splits."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd  # type: ignore[import-untyped]
import pyarrow.parquet as pq


@dataclass(frozen=True, slots=True)
class SupervisedCoverageConfig:
    dataset_dir: Path
    output_path: Path | None = None
    batch_size: int = 65_536
    min_train_rows_per_variant: int = 90


def analyze_supervised_coverage(config: SupervisedCoverageConfig) -> dict[str, Any]:
    metadata = _read_json(config.dataset_dir / "metadata.json")
    target_column = str(metadata["target_column"])
    date_column = str(metadata["date_column"])
    columns = ("variant_id", "item_key", date_column, target_column)

    split_frames = {
        split: _variant_coverage(
            config.dataset_dir / f"{split}.parquet",
            columns=columns,
            date_column=date_column,
            target_column=target_column,
            batch_size=config.batch_size,
        )
        for split in ("train", "validation", "test")
    }
    split_reports = {
        split: _split_report(
            frame,
            min_train_rows_per_variant=config.min_train_rows_per_variant,
        )
        for split, frame in split_frames.items()
    }
    cross_split = _cross_split_report(split_frames)
    recommendations = _recommendations(
        split_reports=split_reports,
        cross_split=cross_split,
        min_train_rows_per_variant=config.min_train_rows_per_variant,
    )
    report = {
        "schema_version": "supervised_coverage.v1",
        "dataset_dir": str(config.dataset_dir),
        "target_column": target_column,
        "date_column": date_column,
        "min_train_rows_per_variant": config.min_train_rows_per_variant,
        "splits": split_reports,
        "cross_split": cross_split,
        "recommendations": recommendations,
    }
    output_path = config.output_path or config.dataset_dir / "coverage_report.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(_jsonable(report), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return report


def _variant_coverage(
    path: Path,
    *,
    columns: tuple[str, ...],
    date_column: str,
    target_column: str,
    batch_size: int,
) -> pd.DataFrame:
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")
    parquet_file = pq.ParquetFile(path)  # type: ignore[no-untyped-call]
    frames: list[pd.DataFrame] = []
    for batch in parquet_file.iter_batches(batch_size=batch_size, columns=list(columns)):  # type: ignore[no-untyped-call]
        frame = batch.to_pandas()
        if frame.empty:
            continue
        grouped = frame.groupby("variant_id", dropna=False).agg(
            item_key=("item_key", "first"),
            rows=("variant_id", "size"),
            min_date=(date_column, "min"),
            max_date=(date_column, "max"),
            positives=(target_column, "sum"),
        )
        frames.append(grouped.reset_index())
    if not frames:
        return pd.DataFrame(
            columns=("variant_id", "item_key", "rows", "min_date", "max_date", "positives")
        )
    combined = pd.concat(frames, ignore_index=True)
    merged = combined.groupby("variant_id", dropna=False).agg(
        item_key=("item_key", "first"),
        rows=("rows", "sum"),
        min_date=("min_date", "min"),
        max_date=("max_date", "max"),
        positives=("positives", "sum"),
    )
    return merged.reset_index()


def _split_report(
    frame: pd.DataFrame,
    *,
    min_train_rows_per_variant: int,
) -> dict[str, Any]:
    if frame.empty:
        return {
            "rows": 0,
            "variants": 0,
            "target_rate": None,
            "min_date": None,
            "max_date": None,
            "rows_per_variant": {},
            "variants_below_min_train_rows": 0,
            "variants_with_less_than_30_rows": 0,
        }
    rows = pd.to_numeric(frame["rows"], errors="coerce").fillna(0)
    positives = pd.to_numeric(frame["positives"], errors="coerce").fillna(0)
    return {
        "rows": int(rows.sum()),
        "variants": int(len(frame)),
        "target_rate": _safe_fraction(float(positives.sum()), float(rows.sum())),
        "min_date": _iso_or_none(frame["min_date"].min()),
        "max_date": _iso_or_none(frame["max_date"].max()),
        "rows_per_variant": {
            "min": _finite_or_none(rows.min()),
            "p10": _finite_or_none(rows.quantile(0.10)),
            "p25": _finite_or_none(rows.quantile(0.25)),
            "p50": _finite_or_none(rows.quantile(0.50)),
            "p75": _finite_or_none(rows.quantile(0.75)),
            "p90": _finite_or_none(rows.quantile(0.90)),
            "max": _finite_or_none(rows.max()),
        },
        "variants_below_min_train_rows": int((rows < min_train_rows_per_variant).sum()),
        "variants_with_less_than_30_rows": int((rows < 30).sum()),
    }


def _cross_split_report(split_frames: dict[str, pd.DataFrame]) -> dict[str, Any]:
    variants = {
        split: set(frame["variant_id"].astype(str).tolist())
        for split, frame in split_frames.items()
    }
    train = variants["train"]
    validation = variants["validation"]
    test = variants["test"]
    all_three = train & validation & test
    return {
        "train_variants": len(train),
        "validation_variants": len(validation),
        "test_variants": len(test),
        "variants_in_all_splits": len(all_three),
        "validation_variants_missing_from_train": len(validation - train),
        "test_variants_missing_from_train": len(test - train),
        "train_variants_missing_validation": len(train - validation),
        "train_variants_missing_test": len(train - test),
        "train_variant_validation_overlap_rate": _safe_fraction(
            len(train & validation),
            len(train),
        ),
        "train_variant_test_overlap_rate": _safe_fraction(len(train & test), len(train)),
    }


def _recommendations(
    *,
    split_reports: dict[str, dict[str, Any]],
    cross_split: dict[str, Any],
    min_train_rows_per_variant: int,
) -> list[str]:
    recommendations = [
        "Keep the chronological split: it respects market time and avoids future leakage.",
        "Use validation for model and hyperparameter selection; keep test untouched for "
        "final reporting.",
    ]
    train_report = split_reports["train"]
    if int(train_report["variants_below_min_train_rows"]) > 0:
        recommendations.append(
            f"Consider filtering training variants below {min_train_rows_per_variant} rows or "
            "adding a missing-coverage feature; sparse variants can make categorical effects noisy."
        )
    if int(cross_split["validation_variants_missing_from_train"]) > 0:
        recommendations.append(
            "Some validation variants are unseen in train; prefer encoders with unknown-category "
            "handling and avoid naive target encoding without cross-fitting."
        )
    if int(cross_split["test_variants_missing_from_train"]) > 0:
        recommendations.append(
            "Some test variants are unseen in train; report metrics both overall and on "
            "seen variants."
        )
    recommendations.append(
        "Train first on sampled rows for hyperparameter search, then rerun the winning "
        "candidates on larger samples or the full train split."
    )
    return recommendations


def _read_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _safe_fraction(numerator: float | int, denominator: float | int) -> float | None:
    return None if denominator == 0 else float(numerator) / float(denominator)


def _iso_or_none(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _finite_or_none(value: Any) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric if math.isfinite(numeric) else None


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, set):
        return sorted(str(item) for item in value)
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value

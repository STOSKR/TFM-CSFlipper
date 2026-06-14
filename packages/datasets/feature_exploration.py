"""Feature exploration utilities for supervised market datasets."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd  # type: ignore[import-untyped]
import pyarrow.parquet as pq


@dataclass(frozen=True, slots=True)
class FeatureExplorationConfig:
    dataset_dir: Path
    output_path: Path | None = None
    sample_rows_per_split: int = 200_000
    batch_size: int = 65_536
    high_cardinality_threshold: int = 100
    drift_smd_threshold: float = 0.5
    redundancy_threshold: float = 0.95
    leakage_auc_threshold: float = 0.97


def explore_supervised_features(config: FeatureExplorationConfig) -> dict[str, Any]:
    metadata = _read_json(config.dataset_dir / "metadata.json")
    target_column = str(metadata["target_column"])
    feature_columns = tuple(str(column) for column in metadata["feature_columns"])
    numeric_features = tuple(str(column) for column in metadata["numeric_features"])
    categorical_features = tuple(str(column) for column in metadata["categorical_features"])
    columns = (*feature_columns, target_column)

    samples = {
        split: _sample_parquet(
            config.dataset_dir / f"{split}.parquet",
            columns=columns,
            max_rows=config.sample_rows_per_split,
            batch_size=config.batch_size,
        )
        for split in ("train", "validation", "test")
    }
    train = samples["train"]

    numeric_report = [
        _numeric_feature_report(
            feature,
            samples=samples,
            target_column=target_column,
        )
        for feature in numeric_features
    ]
    numeric_report.sort(
        key=lambda item: float(item["train_directional_auc"] or 0.0),
        reverse=True,
    )

    categorical_report = [
        _categorical_feature_report(
            feature,
            samples=samples,
            target_column=target_column,
            high_cardinality_threshold=config.high_cardinality_threshold,
        )
        for feature in categorical_features
    ]
    categorical_report.sort(key=lambda item: int(item["train_cardinality"]), reverse=True)

    redundancy_pairs = _numeric_redundancy_pairs(
        train,
        numeric_features=numeric_features,
        threshold=config.redundancy_threshold,
    )
    recommendations = _recommendations(
        numeric_report=numeric_report,
        categorical_report=categorical_report,
        redundancy_pairs=redundancy_pairs,
        config=config,
    )
    report = {
        "schema_version": "supervised_feature_exploration.v1",
        "dataset_dir": str(config.dataset_dir),
        "sample_rows_per_split": {
            split: int(len(sample)) for split, sample in samples.items()
        },
        "target_column": target_column,
        "target_rate_by_split": {
            split: _target_rate(sample[target_column]) for split, sample in samples.items()
        },
        "numeric_features": numeric_report,
        "categorical_features": categorical_report,
        "redundant_numeric_pairs": redundancy_pairs,
        "recommendations": recommendations,
    }
    output_path = config.output_path or config.dataset_dir / "feature_exploration.json"
    output_path.write_text(
        json.dumps(_jsonable(report), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return report


def _sample_parquet(
    path: Path,
    *,
    columns: tuple[str, ...],
    max_rows: int,
    batch_size: int,
) -> pd.DataFrame:
    if max_rows <= 0:
        raise ValueError("sample_rows_per_split must be positive")
    parquet_file = pq.ParquetFile(path)  # type: ignore[no-untyped-call]
    total_rows = parquet_file.metadata.num_rows
    if total_rows == 0:
        return pd.DataFrame(columns=columns)
    step = max(1, math.ceil(total_rows / max_rows))
    frames: list[pd.DataFrame] = []
    row_offset = 0
    for batch in parquet_file.iter_batches(  # type: ignore[no-untyped-call]
        batch_size=batch_size,
        columns=list(columns),
    ):
        frame = batch.to_pandas()
        global_index = np.arange(row_offset, row_offset + len(frame))
        selected = (global_index % step) == 0
        if np.any(selected):
            frames.append(frame.loc[selected])
        row_offset += len(frame)
    if not frames:
        return pd.DataFrame(columns=columns)
    sample = pd.concat(frames, ignore_index=True)
    return sample.head(max_rows)


def _numeric_feature_report(
    feature: str,
    *,
    samples: dict[str, pd.DataFrame],
    target_column: str,
) -> dict[str, Any]:
    train = samples["train"]
    train_values = pd.to_numeric(train[feature], errors="coerce")
    train_target = pd.to_numeric(train[target_column], errors="coerce")
    train_valid = train_values.notna() & train_target.notna()
    train_clean_values = train_values[train_valid]
    train_clean_target = train_target[train_valid]
    train_std = float(train_clean_values.std(ddof=0) or 0.0)
    train_target_std = float(train_clean_target.std(ddof=0) or 0.0)
    train_correlation = (
        train_clean_values.corr(train_clean_target)
        if train_std > 0 and train_target_std > 0
        else None
    )
    validation_smd = _standardized_mean_difference(
        train_clean_values,
        pd.to_numeric(samples["validation"][feature], errors="coerce"),
    )
    test_smd = _standardized_mean_difference(
        train_clean_values,
        pd.to_numeric(samples["test"][feature], errors="coerce"),
    )
    return {
        "feature": feature,
        "train_null_fraction": _null_fraction(train_values),
        "validation_null_fraction": _null_fraction(samples["validation"][feature]),
        "test_null_fraction": _null_fraction(samples["test"][feature]),
        "train_mean": _finite_or_none(train_clean_values.mean()),
        "train_std": _finite_or_none(train_std),
        "train_min": _finite_or_none(train_clean_values.min()),
        "train_p50": _finite_or_none(train_clean_values.quantile(0.5)),
        "train_max": _finite_or_none(train_clean_values.max()),
        "train_correlation": _finite_or_none(train_correlation),
        "train_auc": _finite_or_none(_univariate_auc(train_clean_values, train_clean_target)),
        "train_directional_auc": _finite_or_none(
            _directional_auc(_univariate_auc(train_clean_values, train_clean_target))
        ),
        "validation_smd_vs_train": _finite_or_none(validation_smd),
        "test_smd_vs_train": _finite_or_none(test_smd),
    }


def _categorical_feature_report(
    feature: str,
    *,
    samples: dict[str, pd.DataFrame],
    target_column: str,
    high_cardinality_threshold: int,
) -> dict[str, Any]:
    train = samples["train"]
    train_values = train[feature].astype("string")
    target = pd.to_numeric(train[target_column], errors="coerce")
    cardinality = int(train_values.nunique(dropna=True))
    top_target_rates = _top_category_target_rates(train_values, target)
    return {
        "feature": feature,
        "train_cardinality": cardinality,
        "high_cardinality": cardinality > high_cardinality_threshold,
        "train_null_fraction": _null_fraction(train_values),
        "validation_null_fraction": _null_fraction(samples["validation"][feature]),
        "test_null_fraction": _null_fraction(samples["test"][feature]),
        "validation_js_divergence_vs_train": _finite_or_none(
            _categorical_js_divergence(train_values, samples["validation"][feature])
        ),
        "test_js_divergence_vs_train": _finite_or_none(
            _categorical_js_divergence(train_values, samples["test"][feature])
        ),
        "top_target_rates": top_target_rates,
    }


def _top_category_target_rates(
    values: pd.Series[Any],
    target: pd.Series[Any],
    *,
    limit: int = 12,
) -> list[dict[str, Any]]:
    frame = pd.DataFrame({"value": values, "target": target}).dropna()
    if frame.empty:
        return []
    grouped = frame.groupby("value", dropna=True)["target"].agg(["count", "mean"])
    grouped = grouped.sort_values(["count", "mean"], ascending=[False, False]).head(limit)
    return [
        {
            "value": str(index),
            "count": int(row["count"]),
            "target_rate": float(row["mean"]),
        }
        for index, row in grouped.iterrows()
    ]


def _numeric_redundancy_pairs(
    frame: pd.DataFrame,
    *,
    numeric_features: tuple[str, ...],
    threshold: float,
) -> list[dict[str, Any]]:
    if len(numeric_features) < 2 or frame.empty:
        return []
    numeric_frame = frame.loc[:, list(numeric_features)].apply(pd.to_numeric, errors="coerce")
    numeric_frame = numeric_frame.loc[:, numeric_frame.nunique(dropna=True) > 1]
    numeric_features = tuple(numeric_frame.columns)
    if len(numeric_features) < 2:
        return []
    correlations = numeric_frame.corr().abs()
    pairs: list[dict[str, Any]] = []
    for left_index, left in enumerate(numeric_features):
        for right in numeric_features[left_index + 1 :]:
            correlation = correlations.loc[left, right]
            if pd.notna(correlation) and float(correlation) >= threshold:
                pairs.append(
                    {
                        "left": left,
                        "right": right,
                        "abs_correlation": float(correlation),
                    }
                )
    pairs.sort(key=lambda item: item["abs_correlation"], reverse=True)
    return pairs


def _recommendations(
    *,
    numeric_report: list[dict[str, Any]],
    categorical_report: list[dict[str, Any]],
    redundancy_pairs: list[dict[str, Any]],
    config: FeatureExplorationConfig,
) -> dict[str, Any]:
    leakage_suspects = [
        item["feature"]
        for item in numeric_report
        if float(item["train_directional_auc"] or 0.0) >= config.leakage_auc_threshold
        or abs(float(item["train_correlation"] or 0.0)) >= 0.8
    ]
    high_drift = [
        item["feature"]
        for item in numeric_report
        if max(
            abs(float(item["validation_smd_vs_train"] or 0.0)),
            abs(float(item["test_smd_vs_train"] or 0.0)),
        )
        >= config.drift_smd_threshold
    ]
    strong_numeric = [
        item["feature"]
        for item in numeric_report
        if float(item["train_directional_auc"] or 0.0) >= 0.56
        or abs(float(item["train_correlation"] or 0.0)) >= 0.05
    ]
    weak_numeric = [
        item["feature"]
        for item in numeric_report
        if float(item["train_directional_auc"] or 0.5) < 0.52
        and abs(float(item["train_correlation"] or 0.0)) < 0.02
    ]
    high_cardinality = [
        item["feature"] for item in categorical_report if bool(item["high_cardinality"])
    ]
    low_cardinality = [
        item["feature"] for item in categorical_report if not bool(item["high_cardinality"])
    ]
    redundant_drop_candidates = sorted(
        {
            str(pair["right"])
            for pair in redundancy_pairs
            if str(pair["right"]) not in strong_numeric
        }
    )
    return {
        "leakage_suspects": leakage_suspects,
        "high_drift_numeric_features": high_drift,
        "strong_univariate_numeric_features": strong_numeric,
        "weak_univariate_numeric_features": weak_numeric,
        "high_cardinality_categoricals": high_cardinality,
        "low_cardinality_categoricals": low_cardinality,
        "redundant_numeric_drop_candidates": redundant_drop_candidates,
        "engineering_plan": [
            "Train first models with all non-leakage features, then compare against a "
            "reduced set that drops weak and redundant numeric features.",
            "One-hot encode low-cardinality categoricals; use frequency or cross-fitted "
            "target encoding for high-cardinality categoricals only inside CV folds.",
            "Test interactions between momentum, RSI and volatility features.",
            "Validate drift-heavy features separately before allowing them into production.",
            "Keep calibration metrics central, because weak raw signal can still be useful as "
            "probability input for later decision/RL layers.",
        ],
    }


def _univariate_auc(values: pd.Series[Any], target: pd.Series[Any]) -> float | None:
    clean = pd.DataFrame({"value": values, "target": target}).dropna()
    if clean.empty:
        return None
    positives = int((clean["target"] >= 0.5).sum())
    negatives = int(len(clean) - positives)
    if positives == 0 or negatives == 0:
        return None
    ranks = clean["value"].rank(method="average")
    positive_rank_sum = float(ranks[clean["target"] >= 0.5].sum())
    return (positive_rank_sum - positives * (positives + 1) / 2) / (positives * negatives)


def _directional_auc(auc: float | None) -> float | None:
    if auc is None:
        return None
    return max(auc, 1.0 - auc)


def _standardized_mean_difference(train: pd.Series[Any], other: pd.Series[Any]) -> float | None:
    train_clean = pd.to_numeric(train, errors="coerce").dropna()
    other_clean = pd.to_numeric(other, errors="coerce").dropna()
    if train_clean.empty or other_clean.empty:
        return None
    train_std = float(train_clean.std(ddof=0))
    if train_std == 0:
        return None
    return (float(other_clean.mean()) - float(train_clean.mean())) / train_std


def _categorical_js_divergence(train: pd.Series[Any], other: pd.Series[Any]) -> float | None:
    train_dist = _category_distribution(train)
    other_dist = _category_distribution(other)
    categories = sorted(set(train_dist) | set(other_dist))
    if not categories:
        return None
    p = np.asarray([train_dist.get(category, 0.0) for category in categories], dtype=float)
    q = np.asarray([other_dist.get(category, 0.0) for category in categories], dtype=float)
    m = (p + q) / 2
    return float((_kl_divergence(p, m) + _kl_divergence(q, m)) / 2)


def _category_distribution(values: pd.Series[Any]) -> dict[str, float]:
    clean = values.astype("string").dropna()
    if clean.empty:
        return {}
    counts = clean.value_counts(normalize=True)
    return {str(index): float(value) for index, value in counts.items()}


def _kl_divergence(
    left: np.ndarray[Any, np.dtype[np.float64]],
    right: np.ndarray[Any, np.dtype[np.float64]],
) -> float:
    mask = left > 0
    if not np.any(mask):
        return 0.0
    return float(np.sum(left[mask] * np.log(left[mask] / right[mask])))


def _target_rate(values: pd.Series[Any]) -> float | None:
    clean = pd.to_numeric(values, errors="coerce").dropna()
    if clean.empty:
        return None
    return float(clean.mean())


def _null_fraction(values: pd.Series[Any]) -> float:
    if len(values) == 0:
        return 0.0
    return float(values.isna().mean())


def _finite_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric if math.isfinite(numeric) else None


def _read_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value

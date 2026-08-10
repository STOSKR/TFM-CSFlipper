"""Supervised model training experiments for the direction dataset."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd  # type: ignore[import-untyped]
import pyarrow.parquet as pq

EVALUATION_THRESHOLDS = (0.5, 0.6, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95)
GROUP_ONLY_FEATURES = (
    "primary_item_key",
    "weapon_wear_key",
    "skin_wear_key",
    "collection_rarity_key",
    "rarity_wear_key",
)


@dataclass(frozen=True, slots=True)
class SupervisedTrainingConfig:
    dataset_dir: Path
    output_dir: Path
    max_train_rows: int = 200_000
    max_validation_rows: int = 100_000
    max_test_rows: int = 100_000
    batch_size: int = 65_536
    cv_splits: int = 3
    calibration_method: str = "isotonic"
    random_state: int = 42
    models: tuple[str, ...] = ("dummy", "logistic", "random_forest", "hist_gradient_boosting")
    exclude_features: tuple[str, ...] = ()
    exclude_feature_suffixes: tuple[str, ...] = ()
    include_group_identity_features: bool = False
    selection_metric: str = "precision_at_threshold"
    selection_threshold: float = 0.8
    min_selection_signals: int = 50
    augmentation: str = "none"
    augmentation_ratio: float = 1.0
    augmentation_noise_fraction: float = 0.01


def train_supervised_models(config: SupervisedTrainingConfig) -> dict[str, Any]:
    sklearn = _sklearn()
    metadata = _read_json(config.dataset_dir / "metadata.json")
    target_column = str(metadata["target_column"])
    date_column = str(metadata["date_column"])
    primary_group_column = metadata.get("primary_group_column")
    group_column = str(primary_group_column) if primary_group_column else None
    default_excluded_features = (
        () if config.include_group_identity_features else GROUP_ONLY_FEATURES
    )
    excluded_features = (*default_excluded_features, *config.exclude_features)
    numeric_features = _filter_features(
        tuple(str(column) for column in metadata["numeric_features"]),
        exclude_features=excluded_features,
        exclude_feature_suffixes=config.exclude_feature_suffixes,
    )
    categorical_features = _filter_features(
        tuple(str(column) for column in metadata["categorical_features"]),
        exclude_features=excluded_features,
        exclude_feature_suffixes=config.exclude_feature_suffixes,
    )
    trace_columns = tuple(str(column) for column in metadata["trace_columns"])
    feature_columns = (*numeric_features, *categorical_features)
    loaded_columns = _unique_columns(
        (
            *trace_columns,
            *feature_columns,
            *((group_column,) if group_column else ()),
            target_column,
        )
    )

    train = _sample_parquet(
        config.dataset_dir / "train.parquet",
        columns=loaded_columns,
        max_rows=config.max_train_rows,
        batch_size=config.batch_size,
        sort_column=date_column,
    )
    validation = _sample_parquet(
        config.dataset_dir / "validation.parquet",
        columns=loaded_columns,
        max_rows=config.max_validation_rows,
        batch_size=config.batch_size,
        sort_column=date_column,
    )
    test = _sample_parquet(
        config.dataset_dir / "test.parquet",
        columns=loaded_columns,
        max_rows=config.max_test_rows,
        batch_size=config.batch_size,
        sort_column=date_column,
    )
    datasets = {
        "train": train,
        "validation": validation,
        "test": test,
    }
    _validate_training_frames(datasets, target_column=target_column)
    fit_train = _augment_training_frame(
        train,
        numeric_features=numeric_features,
        date_column=date_column,
        augmentation=config.augmentation,
        ratio=config.augmentation_ratio,
        noise_fraction=config.augmentation_noise_fraction,
        random_state=config.random_state,
    )

    candidates = _candidate_pipelines(
        model_names=config.models,
        numeric_features=numeric_features,
        categorical_features=categorical_features,
        random_state=config.random_state,
    )
    candidate_reports = []
    for candidate_name, pipeline in candidates:
        cv_metrics = _cross_validate_candidate(
            sklearn,
            pipeline,
            train,
            feature_columns=feature_columns,
            target_column=target_column,
            group_column=group_column,
            date_column=date_column,
            include_time_windows=False,
            cv_splits=config.cv_splits,
        )
        fitted = sklearn["clone"](pipeline)
        fitted.fit(
            fit_train.loc[:, feature_columns],
            fit_train[target_column].astype(int),
        )
        validation_metrics = _evaluate_classifier(
            sklearn,
            fitted,
            validation,
            feature_columns=feature_columns,
            target_column=target_column,
            group_column=group_column,
            date_column=None,
            include_time_windows=False,
        )
        candidate_reports.append(
            {
                "candidate": candidate_name,
                "cv": cv_metrics,
                "validation": validation_metrics,
            }
        )

    best_report = _select_best_candidate(
        candidate_reports,
        metric=config.selection_metric,
        threshold=config.selection_threshold,
        min_signals=config.min_selection_signals,
    )
    best_pipeline = dict(candidates)[str(best_report["candidate"])]
    calibrated = sklearn["CalibratedClassifierCV"](
        estimator=best_pipeline,
        method=config.calibration_method,
        cv=_date_aware_time_series_splits(
            sklearn,
            fit_train,
            date_column=date_column,
            cv_splits=config.cv_splits,
        ),
    )
    calibrated.fit(
        fit_train.loc[:, feature_columns],
        fit_train[target_column].astype(int),
    )
    calibrated_validation = _evaluate_classifier(
        sklearn,
        calibrated,
        validation,
        feature_columns=feature_columns,
        target_column=target_column,
        group_column=group_column,
        date_column=date_column,
        include_time_windows=True,
    )
    calibrated_test = _evaluate_classifier(
        sklearn,
        calibrated,
        test,
        feature_columns=feature_columns,
        target_column=target_column,
        group_column=group_column,
        date_column=date_column,
        include_time_windows=True,
    )
    decision_threshold = _select_decision_threshold(
        validation_report=calibrated_validation,
        test_report=calibrated_test,
        min_signals=config.min_selection_signals,
    )

    config.output_dir.mkdir(parents=True, exist_ok=True)
    model_path = config.output_dir / "calibrated_model.joblib"
    sklearn["joblib"].dump(calibrated, model_path)
    report = dict[str, Any]({
        "schema_version": "supervised_training_experiment.v1",
        "created_at": datetime.now(tz=UTC).isoformat(),
        "dataset_dir": str(config.dataset_dir),
        "output_dir": str(config.output_dir),
        "model_path": str(model_path),
        "target_column": target_column,
        "feature_columns": list(feature_columns),
        "numeric_features": list(numeric_features),
        "categorical_features": list(categorical_features),
        "primary_group_column": group_column,
        "group_only_features": list(default_excluded_features),
        "excluded_training_features": sorted(
            set(str(column) for column in metadata["feature_columns"]) - set(feature_columns)
        ),
        "row_counts": {split: int(len(frame)) for split, frame in datasets.items()},
        "fit_train_rows": int(len(fit_train)),
        "augmentation": {
            "method": config.augmentation,
            "ratio": config.augmentation_ratio,
            "noise_fraction": config.augmentation_noise_fraction,
            "applied_to": "train_only",
            "validation_and_test_untouched": True,
        },
        "target_rates": {
            split: float(frame[target_column].astype(float).mean())
            for split, frame in datasets.items()
        },
        "candidate_reports": candidate_reports,
        "selected_candidate": best_report["candidate"],
        "selection": {
            "metric": config.selection_metric,
            "threshold": config.selection_threshold,
            "min_signals": config.min_selection_signals,
            "reason": best_report["selection_reason"],
            "score": best_report["selection_score"],
        },
        "selection_reason": best_report["selection_reason"],
        "decision_threshold": decision_threshold,
        "calibration": {
            "method": config.calibration_method,
            "validation": calibrated_validation,
            "test": calibrated_test,
        },
    })
    (config.output_dir / "training_report.json").write_text(
        json.dumps(_jsonable(report), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return report


def _candidate_pipelines(
    *,
    model_names: tuple[str, ...],
    numeric_features: tuple[str, ...],
    categorical_features: tuple[str, ...],
    random_state: int,
) -> list[tuple[str, Any]]:
    sklearn = _sklearn()
    pipelines: list[tuple[str, Any]] = []
    requested = set(model_names)
    if "dummy" in requested:
        pipelines.append(
            (
                "dummy_prior",
                sklearn["Pipeline"](
                    [
                        (
                            "preprocess",
                            _linear_preprocessor(
                                sklearn,
                                numeric_features,
                                categorical_features,
                            ),
                        ),
                        ("model", sklearn["DummyClassifier"](strategy="prior")),
                    ]
                ),
            )
        )
    if "logistic" in requested:
        for c_value in (DecimalFloat("0.3"), DecimalFloat("1.0"), DecimalFloat("3.0")):
            pipelines.append(
                (
                    f"logistic_l2_c{c_value.label}",
                    sklearn["Pipeline"](
                        [
                            (
                                "preprocess",
                                _linear_preprocessor(
                                    sklearn,
                                    numeric_features,
                                    categorical_features,
                                ),
                            ),
                            (
                                "model",
                                sklearn["LogisticRegression"](
                                    C=c_value.value,
                                    class_weight="balanced",
                                    max_iter=500,
                                    random_state=random_state,
                                ),
                            ),
                        ]
                    ),
                )
            )
    if "random_forest" in requested:
        for max_depth in (10, 18):
            pipelines.append(
                (
                    f"random_forest_depth{max_depth}",
                    sklearn["Pipeline"](
                        [
                            (
                                "preprocess",
                                _tree_preprocessor(
                                    sklearn,
                                    numeric_features,
                                    categorical_features,
                                ),
                            ),
                            (
                                "model",
                                sklearn["RandomForestClassifier"](
                                    n_estimators=160,
                                    max_depth=max_depth,
                                    min_samples_leaf=5,
                                    class_weight="balanced_subsample",
                                    n_jobs=-1,
                                    random_state=random_state,
                                ),
                            ),
                        ]
                    ),
                )
            )
    if "hist_gradient_boosting" in requested:
        for learning_rate in (DecimalFloat("0.05"), DecimalFloat("0.1")):
            pipelines.append(
                (
                    f"hist_gradient_boosting_lr{learning_rate.label}",
                    sklearn["Pipeline"](
                        [
                            (
                                "preprocess",
                                _tree_preprocessor(
                                    sklearn,
                                    numeric_features,
                                    categorical_features,
                                ),
                            ),
                            (
                                "model",
                                sklearn["HistGradientBoostingClassifier"](
                                    learning_rate=learning_rate.value,
                                    max_iter=160,
                                    max_leaf_nodes=31,
                                    l2_regularization=0.0,
                                    random_state=random_state,
                                ),
                            ),
                        ]
                    ),
                )
            )
    if not pipelines:
        raise ValueError("no training candidates selected")
    return pipelines


def _filter_features(
    features: tuple[str, ...],
    *,
    exclude_features: tuple[str, ...],
    exclude_feature_suffixes: tuple[str, ...],
) -> tuple[str, ...]:
    excluded = set(exclude_features)
    return tuple(
        feature
        for feature in features
        if feature not in excluded
        and not any(feature.endswith(suffix) for suffix in exclude_feature_suffixes)
    )


def _unique_columns(columns: tuple[str, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    unique = []
    for column in columns:
        if column in seen:
            continue
        seen.add(column)
        unique.append(column)
    return tuple(unique)


@dataclass(frozen=True, slots=True)
class DecimalFloat:
    raw: str

    @property
    def value(self) -> float:
        return float(self.raw)

    @property
    def label(self) -> str:
        return self.raw.replace(".", "_")


def _linear_preprocessor(
    sklearn: dict[str, Any],
    numeric_features: tuple[str, ...],
    categorical_features: tuple[str, ...],
) -> Any:
    return sklearn["ColumnTransformer"](
        [
            (
                "numeric",
                sklearn["Pipeline"](
                    [
                        ("imputer", sklearn["SimpleImputer"](strategy="median")),
                        ("scaler", sklearn["StandardScaler"]()),
                    ]
                ),
                list(numeric_features),
            ),
            (
                "categorical",
                sklearn["OneHotEncoder"](handle_unknown="ignore"),
                list(categorical_features),
            ),
        ]
    )


def _tree_preprocessor(
    sklearn: dict[str, Any],
    numeric_features: tuple[str, ...],
    categorical_features: tuple[str, ...],
) -> Any:
    return sklearn["ColumnTransformer"](
        [
            (
                "numeric",
                sklearn["SimpleImputer"](strategy="median"),
                list(numeric_features),
            ),
            (
                "categorical",
                sklearn["OrdinalEncoder"](
                    handle_unknown="use_encoded_value",
                    unknown_value=-1,
                    encoded_missing_value=-1,
                ),
                list(categorical_features),
            ),
        ],
        verbose_feature_names_out=False,
    )


def _cross_validate_candidate(
    sklearn: dict[str, Any],
    pipeline: Any,
    train: pd.DataFrame,
    *,
    feature_columns: tuple[str, ...],
    target_column: str,
    group_column: str | None,
    date_column: str | None,
    include_time_windows: bool,
    cv_splits: int,
) -> dict[str, Any]:
    if cv_splits < 2:
        return {"splits": 0}
    fold_metrics = []
    features = train.loc[:, feature_columns]
    target = train[target_column].astype(int)
    splits = _date_aware_time_series_splits(
        sklearn,
        train,
        date_column=date_column,
        cv_splits=cv_splits,
    )
    for fold_index, (train_index, validation_index) in enumerate(splits, start=1):
        fold_model = sklearn["clone"](pipeline)
        fold_model.fit(features.iloc[train_index], target.iloc[train_index])
        fold_frame = train.iloc[validation_index]
        metrics = _evaluate_classifier(
            sklearn,
            fold_model,
            fold_frame,
            feature_columns=feature_columns,
            target_column=target_column,
            group_column=group_column,
            date_column=date_column,
            include_time_windows=include_time_windows,
        )
        metrics["fold"] = fold_index
        fold_metrics.append(metrics)
    return {
        "splits": cv_splits,
        "folds": fold_metrics,
        "mean_roc_auc": _mean_metric(fold_metrics, "roc_auc"),
        "mean_average_precision": _mean_metric(fold_metrics, "average_precision"),
        "mean_brier_score": _mean_metric(fold_metrics, "brier_score"),
    }


def _augment_training_frame(
    train: pd.DataFrame,
    *,
    numeric_features: tuple[str, ...],
    date_column: str,
    augmentation: str,
    ratio: float,
    noise_fraction: float,
    random_state: int,
) -> pd.DataFrame:
    """Create train-only numerical jitter without altering labels or dates.

    The generated rows retain the source timestamp. Date-aware folds keep all
    observations from a given date on the same side of every temporal split.
    Validation and test never pass through this function.
    """
    if augmentation == "none":
        return train
    if augmentation != "gaussian_jitter":
        raise ValueError(f"unknown augmentation method: {augmentation}")
    if ratio <= 0:
        raise ValueError("augmentation_ratio must be greater than zero")
    if noise_fraction <= 0:
        raise ValueError("augmentation_noise_fraction must be greater than zero")

    rng = np.random.default_rng(random_state)
    copies = max(1, int(round(ratio)))
    augmented = pd.concat([train.copy() for _ in range(copies)], ignore_index=True)
    for feature in numeric_features:
        values = pd.to_numeric(augmented[feature], errors="coerce")
        finite = values[np.isfinite(values)]
        if finite.empty:
            continue
        spread = float(finite.quantile(0.75) - finite.quantile(0.25))
        if not math.isfinite(spread) or spread == 0:
            continue
        jitter = rng.normal(loc=0.0, scale=spread * noise_fraction, size=len(augmented))
        perturbed = values.to_numpy(dtype=float, copy=True)
        valid = np.isfinite(perturbed)
        perturbed[valid] += jitter[valid]
        if _is_nonnegative_feature(feature):
            perturbed[valid] = np.maximum(perturbed[valid], 0.0)
        augmented[feature] = perturbed
    return _sort_by_time(pd.concat([train, augmented], ignore_index=True), sort_column=date_column)


def _is_nonnegative_feature(feature: str) -> bool:
    return any(token in feature for token in ("price", "count", "quantity", "spread"))


def _date_aware_time_series_splits(
    sklearn: dict[str, Any],
    frame: pd.DataFrame,
    *,
    date_column: str | None,
    cv_splits: int,
) -> list[tuple[np.ndarray[Any, Any], np.ndarray[Any, Any]]]:
    if date_column is not None and date_column in frame:
        date_values = pd.to_datetime(frame[date_column]).dt.normalize()
        unique_dates = np.asarray(sorted(date_values.dropna().unique()))
        if len(unique_dates) > cv_splits:
            splitter = sklearn["TimeSeriesSplit"](n_splits=cv_splits)
            output = []
            for train_dates, validation_dates in splitter.split(unique_dates):
                train_mask = date_values.isin(unique_dates[train_dates]).to_numpy()
                validation_mask = date_values.isin(unique_dates[validation_dates]).to_numpy()
                output.append((np.flatnonzero(train_mask), np.flatnonzero(validation_mask)))
            return output
    splitter = sklearn["TimeSeriesSplit"](n_splits=cv_splits)
    return list(splitter.split(frame))


def _evaluate_classifier(
    sklearn: dict[str, Any],
    model: Any,
    frame: pd.DataFrame,
    *,
    feature_columns: tuple[str, ...],
    target_column: str,
    group_column: str | None = None,
    date_column: str | None = None,
    include_time_windows: bool = False,
) -> dict[str, Any]:
    y_true = frame[target_column].astype(int).to_numpy()
    probabilities = model.predict_proba(frame.loc[:, feature_columns])[:, 1]
    predictions = (probabilities >= 0.5).astype(int)
    precision, recall, f1, _support = sklearn["precision_recall_fscore_support"](
        y_true,
        predictions,
        average="binary",
        zero_division=0,
    )
    report: dict[str, Any] = {
        "rows": int(len(frame)),
        "target_rate": float(np.mean(y_true)),
        "roc_auc": _metric_or_none(lambda: sklearn["roc_auc_score"](y_true, probabilities)),
        "average_precision": _metric_or_none(
            lambda: sklearn["average_precision_score"](y_true, probabilities)
        ),
        "brier_score": _metric_or_none(lambda: sklearn["brier_score_loss"](y_true, probabilities)),
        "log_loss": _metric_or_none(lambda: sklearn["log_loss"](y_true, probabilities)),
        "precision_at_0_5": float(precision),
        "recall_at_0_5": float(recall),
        "f1_at_0_5": float(f1),
        "thresholds": _threshold_metrics(
            sklearn,
            y_true=y_true,
            probabilities=probabilities,
            thresholds=EVALUATION_THRESHOLDS,
        ),
    }
    if group_column is not None and group_column in frame:
        report["primary_group"] = _primary_group_metrics(
            y_true=y_true,
            probabilities=probabilities,
            groups=frame[group_column].astype(str).to_numpy(),
            thresholds=EVALUATION_THRESHOLDS,
            group_column=group_column,
        )
    if include_time_windows and date_column is not None and date_column in frame:
        report["time_windows"] = _time_window_metrics(
            sklearn,
            frame=frame,
            date_column=date_column,
            y_true=y_true,
            probabilities=probabilities,
            thresholds=EVALUATION_THRESHOLDS,
        )
    return report


def _threshold_metrics(
    sklearn: dict[str, Any],
    *,
    y_true: np.ndarray[Any, Any],
    probabilities: np.ndarray[Any, Any],
    thresholds: tuple[float, ...],
) -> list[dict[str, Any]]:
    rows = len(y_true)
    metrics = []
    for threshold in thresholds:
        predictions = (probabilities >= threshold).astype(int)
        precision, recall, f1, _support = sklearn["precision_recall_fscore_support"](
            y_true,
            predictions,
            average="binary",
            zero_division=0,
        )
        predicted_positive = int(np.sum(predictions))
        metrics.append(
            {
                "threshold": threshold,
                "predicted_positive": predicted_positive,
                "predicted_positive_rate": (
                    float(predicted_positive) / rows if rows else None
                ),
                "precision": float(precision),
                "recall": float(recall),
                "f1": float(f1),
            }
        )
    return metrics


def _primary_group_metrics(
    *,
    y_true: np.ndarray[Any, Any],
    probabilities: np.ndarray[Any, Any],
    groups: np.ndarray[Any, Any],
    thresholds: tuple[float, ...],
    group_column: str,
) -> dict[str, Any]:
    summaries = []
    for threshold in thresholds:
        selected = probabilities >= threshold
        selected_groups = groups[selected]
        selected_true = y_true[selected]
        group_precisions = []
        group_signal_counts = []
        for group in np.unique(selected_groups):
            group_mask = selected_groups == group
            signals = int(np.count_nonzero(group_mask))
            if signals == 0:
                continue
            group_signal_counts.append(signals)
            group_precisions.append(float(np.mean(selected_true[group_mask])))

        enough_signal_precisions = [
            precision
            for precision, signals in zip(group_precisions, group_signal_counts, strict=True)
            if signals >= 5
        ]
        summaries.append(
            {
                "threshold": threshold,
                "groups_with_signals": int(len(group_precisions)),
                "groups_with_at_least_5_signals": int(len(enough_signal_precisions)),
                "signals": int(np.count_nonzero(selected)),
                "overall_precision": (
                    float(np.mean(selected_true)) if len(selected_true) else 0.0
                ),
                "group_precision_p10": _percentile_or_none(enough_signal_precisions, 10),
                "group_precision_p50": _percentile_or_none(enough_signal_precisions, 50),
                "group_precision_p90": _percentile_or_none(enough_signal_precisions, 90),
            }
        )
    return {
        "column": group_column,
        "groups": int(len(np.unique(groups))),
        "thresholds": summaries,
    }


def _time_window_metrics(
    sklearn: dict[str, Any],
    *,
    frame: pd.DataFrame,
    date_column: str,
    y_true: np.ndarray[Any, Any],
    probabilities: np.ndarray[Any, Any],
    thresholds: tuple[float, ...],
) -> list[dict[str, Any]]:
    periods = pd.to_datetime(frame[date_column]).dt.to_period("M").astype(str)
    windows = []
    for period in sorted(periods.unique()):
        mask = periods == period
        mask_array = mask.to_numpy()
        window_true = y_true[mask_array]
        window_probabilities = probabilities[mask_array]
        windows.append(
            {
                "period": period,
                "rows": int(len(window_true)),
                "target_rate": float(np.mean(window_true)) if len(window_true) else None,
                "roc_auc": _window_metric(
                    sklearn,
                    "roc_auc_score",
                    window_true,
                    window_probabilities,
                ),
                "average_precision": _window_metric(
                    sklearn,
                    "average_precision_score",
                    window_true,
                    window_probabilities,
                ),
                "thresholds": _threshold_metrics(
                    sklearn,
                    y_true=window_true,
                    probabilities=window_probabilities,
                    thresholds=thresholds,
                ),
            }
        )
    return windows


def _window_metric(
    sklearn: dict[str, Any],
    metric_name: str,
    y_true: np.ndarray[Any, Any],
    probabilities: np.ndarray[Any, Any],
) -> float | None:
    return _metric_or_none(lambda: sklearn[metric_name](y_true, probabilities))


def _select_decision_threshold(
    *,
    validation_report: dict[str, Any],
    test_report: dict[str, Any],
    min_signals: int,
) -> dict[str, Any]:
    eligible = [
        row
        for row in validation_report["thresholds"]
        if int(row["predicted_positive"]) >= min_signals
    ]
    candidates = eligible or list(validation_report["thresholds"])
    selected = max(
        candidates,
        key=lambda row: (
            float(row["precision"]),
            int(row["predicted_positive"]),
            float(row["recall"]),
        ),
    )
    threshold = float(selected["threshold"])
    return {
        "selected_from": "validation",
        "threshold": threshold,
        "min_signals": min_signals,
        "eligible": bool(eligible),
        "validation": selected,
        "test_at_same_threshold": _threshold_report(test_report, threshold=threshold),
    }


def _percentile_or_none(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    return float(np.percentile(np.asarray(values, dtype=np.float64), percentile))


def _select_best_candidate(
    candidate_reports: list[dict[str, Any]],
    *,
    metric: str,
    threshold: float,
    min_signals: int,
) -> dict[str, Any]:
    if metric == "roc_auc":
        return _with_selection(
            max(
                candidate_reports,
                key=lambda item: (
                    float(item["validation"]["roc_auc"] or 0.0),
                    -float(item["validation"]["brier_score"] or 1.0),
                ),
            ),
            reason="highest validation ROC-AUC, then lowest validation Brier score",
            score_name="roc_auc",
        )
    if metric == "average_precision":
        return _with_selection(
            max(
                candidate_reports,
                key=lambda item: (
                    float(item["validation"]["average_precision"] or 0.0),
                    -float(item["validation"]["brier_score"] or 1.0),
                ),
            ),
            reason=(
                "highest validation average precision, then lowest validation Brier score"
            ),
            score_name="average_precision",
        )
    if metric == "precision_at_threshold":
        return _select_by_threshold_precision(
            candidate_reports,
            threshold=threshold,
            min_signals=min_signals,
        )
    raise ValueError(f"unknown selection metric: {metric}")


def _with_selection(
    report: dict[str, Any],
    *,
    reason: str,
    score_name: str,
) -> dict[str, Any]:
    selected = dict(report)
    selected["selection_reason"] = reason
    selected["selection_score"] = selected["validation"].get(score_name)
    return selected


def _select_by_threshold_precision(
    candidate_reports: list[dict[str, Any]],
    *,
    threshold: float,
    min_signals: int,
) -> dict[str, Any]:
    scored = []
    for report in candidate_reports:
        threshold_report = _threshold_report(report["validation"], threshold=threshold)
        signals = int(threshold_report["predicted_positive"])
        precision = float(threshold_report["precision"])
        recall = float(threshold_report["recall"])
        eligible = signals >= min_signals
        scored.append((eligible, precision, signals, recall, report))

    selected = max(
        scored,
        key=lambda item: (
            int(item[0]),
            item[1],
            item[2],
            item[3],
            float(item[4]["validation"]["average_precision"] or 0.0),
        ),
    )
    selected_report = dict(selected[4])
    selected_report["selection_reason"] = (
        f"highest validation precision at threshold {threshold:g} with at least "
        f"{min_signals} validation signals; falls back to highest precision if none qualify"
    )
    selected_report["selection_score"] = {
        "eligible": bool(selected[0]),
        "precision": selected[1],
        "signals": selected[2],
        "recall": selected[3],
        "threshold": threshold,
    }
    return selected_report


def _threshold_report(report: dict[str, Any], *, threshold: float) -> dict[str, Any]:
    thresholds = report.get("thresholds") or []
    if not thresholds:
        raise ValueError("candidate report has no threshold metrics")
    return min(
        thresholds,
        key=lambda row: abs(float(row["threshold"]) - threshold),
    )


def _sample_parquet(
    path: Path,
    *,
    columns: tuple[str, ...],
    max_rows: int,
    batch_size: int,
    sort_column: str,
) -> pd.DataFrame:
    parquet_file = pq.ParquetFile(path)  # type: ignore[no-untyped-call]
    total_rows = parquet_file.metadata.num_rows
    if max_rows <= 0 or max_rows >= total_rows:
        frame = parquet_file.read(columns=list(columns)).to_pandas()  # type: ignore[no-untyped-call]
        return _sort_by_time(frame, sort_column=sort_column)
    step = max(1, math.ceil(total_rows / max_rows))
    frames: list[pd.DataFrame] = []
    row_offset = 0
    for batch in parquet_file.iter_batches(batch_size=batch_size, columns=list(columns)):  # type: ignore[no-untyped-call]
        frame = batch.to_pandas()
        global_index = np.arange(row_offset, row_offset + len(frame))
        selected = (global_index % step) == 0
        if np.any(selected):
            frames.append(frame.loc[selected])
        row_offset += len(frame)
    sample = pd.concat(frames, ignore_index=True).head(max_rows)
    return _sort_by_time(sample, sort_column=sort_column)


def _sort_by_time(frame: pd.DataFrame, *, sort_column: str) -> pd.DataFrame:
    if sort_column in frame:
        return frame.sort_values(sort_column).reset_index(drop=True)
    return frame


def _validate_training_frames(
    frames: dict[str, pd.DataFrame],
    *,
    target_column: str,
) -> None:
    for split, frame in frames.items():
        if frame.empty:
            raise ValueError(f"{split} split is empty")
        target = frame[target_column].dropna().astype(int)
        if target.nunique() < 2:
            raise ValueError(f"{split} split must contain both classes")


def _mean_metric(metrics: list[dict[str, Any]], key: str) -> float | None:
    values = [float(item[key]) for item in metrics if item.get(key) is not None]
    return float(np.mean(values)) if values else None


def _metric_or_none(callback: Any) -> float | None:
    try:
        value = callback()
    except ValueError:
        return None
    return float(value) if math.isfinite(float(value)) else None


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def _sklearn() -> dict[str, Any]:
    try:
        import joblib  # type: ignore[import-untyped]
        from sklearn.base import clone  # type: ignore[import-untyped]
        from sklearn.calibration import CalibratedClassifierCV  # type: ignore[import-untyped]
        from sklearn.compose import ColumnTransformer  # type: ignore[import-untyped]
        from sklearn.dummy import DummyClassifier  # type: ignore[import-untyped]
        from sklearn.ensemble import (  # type: ignore[import-untyped]
            HistGradientBoostingClassifier,
            RandomForestClassifier,
        )
        from sklearn.impute import SimpleImputer  # type: ignore[import-untyped]
        from sklearn.linear_model import LogisticRegression  # type: ignore[import-untyped]
        from sklearn.metrics import (  # type: ignore[import-untyped]
            average_precision_score,
            brier_score_loss,
            log_loss,
            precision_recall_fscore_support,
            roc_auc_score,
        )
        from sklearn.model_selection import TimeSeriesSplit  # type: ignore[import-untyped]
        from sklearn.pipeline import Pipeline  # type: ignore[import-untyped]
        from sklearn.preprocessing import (  # type: ignore[import-untyped]
            OneHotEncoder,
            OrdinalEncoder,
            StandardScaler,
        )
    except ModuleNotFoundError as exc:  # pragma: no cover - depends on local extras
        raise RuntimeError(
            "scikit-learn and joblib are required for training. "
            "Install project dependencies before running this experiment."
        ) from exc
    return {
        "average_precision_score": average_precision_score,
        "brier_score_loss": brier_score_loss,
        "CalibratedClassifierCV": CalibratedClassifierCV,
        "clone": clone,
        "ColumnTransformer": ColumnTransformer,
        "DummyClassifier": DummyClassifier,
        "HistGradientBoostingClassifier": HistGradientBoostingClassifier,
        "joblib": joblib,
        "log_loss": log_loss,
        "LogisticRegression": LogisticRegression,
        "OneHotEncoder": OneHotEncoder,
        "OrdinalEncoder": OrdinalEncoder,
        "Pipeline": Pipeline,
        "precision_recall_fscore_support": precision_recall_fscore_support,
        "RandomForestClassifier": RandomForestClassifier,
        "roc_auc_score": roc_auc_score,
        "SimpleImputer": SimpleImputer,
        "StandardScaler": StandardScaler,
        "TimeSeriesSplit": TimeSeriesSplit,
    }


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value

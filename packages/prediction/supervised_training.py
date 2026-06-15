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

EVALUATION_THRESHOLDS = (0.5, 0.6, 0.7, 0.8, 0.9)


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


def train_supervised_models(config: SupervisedTrainingConfig) -> dict[str, Any]:
    sklearn = _sklearn()
    metadata = _read_json(config.dataset_dir / "metadata.json")
    target_column = str(metadata["target_column"])
    date_column = str(metadata["date_column"])
    numeric_features = tuple(str(column) for column in metadata["numeric_features"])
    categorical_features = tuple(str(column) for column in metadata["categorical_features"])
    trace_columns = tuple(str(column) for column in metadata["trace_columns"])
    columns = (*trace_columns, *numeric_features, *categorical_features, target_column)

    train = _sample_parquet(
        config.dataset_dir / "train.parquet",
        columns=columns,
        max_rows=config.max_train_rows,
        batch_size=config.batch_size,
        sort_column=date_column,
    )
    validation = _sample_parquet(
        config.dataset_dir / "validation.parquet",
        columns=columns,
        max_rows=config.max_validation_rows,
        batch_size=config.batch_size,
        sort_column=date_column,
    )
    test = _sample_parquet(
        config.dataset_dir / "test.parquet",
        columns=columns,
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
    feature_columns = (*numeric_features, *categorical_features)

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
            cv_splits=config.cv_splits,
        )
        fitted = sklearn["clone"](pipeline)
        fitted.fit(train.loc[:, feature_columns], train[target_column].astype(int))
        validation_metrics = _evaluate_classifier(
            sklearn,
            fitted,
            validation,
            feature_columns=feature_columns,
            target_column=target_column,
        )
        candidate_reports.append(
            {
                "candidate": candidate_name,
                "cv": cv_metrics,
                "validation": validation_metrics,
            }
        )

    best_report = _select_best_candidate(candidate_reports)
    best_pipeline = dict(candidates)[str(best_report["candidate"])]
    calibrated = sklearn["CalibratedClassifierCV"](
        estimator=best_pipeline,
        method=config.calibration_method,
        cv=sklearn["TimeSeriesSplit"](n_splits=config.cv_splits),
    )
    calibrated.fit(train.loc[:, feature_columns], train[target_column].astype(int))
    calibrated_validation = _evaluate_classifier(
        sklearn,
        calibrated,
        validation,
        feature_columns=feature_columns,
        target_column=target_column,
    )
    calibrated_test = _evaluate_classifier(
        sklearn,
        calibrated,
        test,
        feature_columns=feature_columns,
        target_column=target_column,
    )

    config.output_dir.mkdir(parents=True, exist_ok=True)
    model_path = config.output_dir / "calibrated_model.joblib"
    sklearn["joblib"].dump(calibrated, model_path)
    report = {
        "schema_version": "supervised_training_experiment.v1",
        "created_at": datetime.now(tz=UTC).isoformat(),
        "dataset_dir": str(config.dataset_dir),
        "output_dir": str(config.output_dir),
        "model_path": str(model_path),
        "target_column": target_column,
        "feature_columns": list(feature_columns),
        "numeric_features": list(numeric_features),
        "categorical_features": list(categorical_features),
        "row_counts": {split: int(len(frame)) for split, frame in datasets.items()},
        "target_rates": {
            split: float(frame[target_column].astype(float).mean())
            for split, frame in datasets.items()
        },
        "candidate_reports": candidate_reports,
        "selected_candidate": best_report["candidate"],
        "selection_reason": "highest validation ROC-AUC, then lowest validation Brier score",
        "calibration": {
            "method": config.calibration_method,
            "validation": calibrated_validation,
            "test": calibrated_test,
        },
    }
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
    cv_splits: int,
) -> dict[str, Any]:
    if cv_splits < 2:
        return {"splits": 0}
    splitter = sklearn["TimeSeriesSplit"](n_splits=cv_splits)
    fold_metrics = []
    features = train.loc[:, feature_columns]
    target = train[target_column].astype(int)
    for fold_index, (train_index, validation_index) in enumerate(splitter.split(features), start=1):
        fold_model = sklearn["clone"](pipeline)
        fold_model.fit(features.iloc[train_index], target.iloc[train_index])
        fold_frame = train.iloc[validation_index]
        metrics = _evaluate_classifier(
            sklearn,
            fold_model,
            fold_frame,
            feature_columns=feature_columns,
            target_column=target_column,
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


def _evaluate_classifier(
    sklearn: dict[str, Any],
    model: Any,
    frame: pd.DataFrame,
    *,
    feature_columns: tuple[str, ...],
    target_column: str,
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
    return {
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


def _select_best_candidate(candidate_reports: list[dict[str, Any]]) -> dict[str, Any]:
    return max(
        candidate_reports,
        key=lambda item: (
            float(item["validation"]["roc_auc"] or 0.0),
            -float(item["validation"]["brier_score"] or 1.0),
        ),
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

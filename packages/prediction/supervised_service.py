"""Service layer for supervised inference responses consumed by MARL/UI flows."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Protocol

import numpy as np
import pandas as pd  # type: ignore[import-untyped]

from packages.prediction.supervised_inference import (
    SupervisedModelArtifact,
    SupervisedPrediction,
)

DEFAULT_SUPERVISED_MODEL_DIR = Path(
    "models/supervised_direction_v1/20260615_operational_default"
)


class SupervisedPredictionSink(Protocol):
    """Optional persistence hook for inference results."""

    def record_supervised_prediction(self, result: SupervisedInferenceResult) -> None:
        """Persist or emit a supervised inference result."""


@dataclass(frozen=True, slots=True)
class SupervisedInferenceResult:
    model_id: str
    prediction_name: str
    probability: Decimal
    threshold: Decimal
    is_signal: bool
    target_column: str
    scored_at: datetime
    observed_at: datetime | None
    feature_snapshot: Mapping[str, Any]
    correlation_id: str | None = None

    @property
    def marl_feature_name(self) -> str:
        return self.prediction_name


@dataclass(frozen=True, slots=True)
class SupervisedBatchInferenceResult:
    model_id: str
    prediction_name: str
    scored_at: datetime
    results: tuple[SupervisedInferenceResult, ...]


class SupervisedInferenceService:
    """Inference-only facade around a versioned supervised model artifact."""

    def __init__(
        self,
        artifact: SupervisedModelArtifact,
        *,
        sink: SupervisedPredictionSink | None = None,
        clock: Any | None = None,
    ) -> None:
        self._artifact = artifact
        self._sink = sink
        self._clock = clock or (lambda: datetime.now(tz=UTC))

    @classmethod
    def load(
        cls,
        artifact_dir: Path = DEFAULT_SUPERVISED_MODEL_DIR,
        *,
        sink: SupervisedPredictionSink | None = None,
        clock: Any | None = None,
    ) -> SupervisedInferenceService:
        return cls(
            SupervisedModelArtifact.load(artifact_dir),
            sink=sink,
            clock=clock,
        )

    @property
    def model_id(self) -> str:
        return self._artifact.metadata.model_id

    @property
    def feature_columns(self) -> tuple[str, ...]:
        return self._artifact.metadata.feature_columns

    def score_features(
        self,
        features: Mapping[str, Any],
        *,
        observed_at: datetime | None = None,
        correlation_id: str | None = None,
    ) -> SupervisedInferenceResult:
        scored_at = self._now()
        prediction = self._artifact.predict_one(dict(features))
        result = self._result(
            prediction,
            features,
            scored_at=scored_at,
            observed_at=observed_at,
            correlation_id=correlation_id,
        )
        self._record(result)
        return result

    def score_frame(
        self,
        frame: pd.DataFrame,
        *,
        observed_at_column: str | None = None,
        correlation_id_column: str | None = None,
    ) -> SupervisedBatchInferenceResult:
        scored_at = self._now()
        predictions = self._artifact.predict_frame(frame)
        results = tuple(
            self._result(
                prediction,
                _row_features(row),
                scored_at=scored_at,
                observed_at=_row_datetime(row, observed_at_column),
                correlation_id=_row_text(row, correlation_id_column),
            )
            for prediction, (_, row) in zip(predictions, frame.iterrows(), strict=True)
        )
        for result in results:
            self._record(result)
        return SupervisedBatchInferenceResult(
            model_id=self.model_id,
            prediction_name=self._artifact.metadata.prediction_name,
            scored_at=scored_at,
            results=results,
        )

    def _result(
        self,
        prediction: SupervisedPrediction,
        features: Mapping[str, Any],
        *,
        scored_at: datetime,
        observed_at: datetime | None,
        correlation_id: str | None,
    ) -> SupervisedInferenceResult:
        return SupervisedInferenceResult(
            model_id=prediction.model_id,
            prediction_name=prediction.prediction_name,
            probability=prediction.probability,
            threshold=prediction.threshold,
            is_signal=prediction.is_signal,
            target_column=self._artifact.metadata.target_column,
            scored_at=scored_at,
            observed_at=observed_at,
            feature_snapshot={
                column: _jsonable(features[column])
                for column in self._artifact.metadata.feature_columns
                if column in features
            },
            correlation_id=correlation_id,
        )

    def _record(self, result: SupervisedInferenceResult) -> None:
        if self._sink is not None:
            self._sink.record_supervised_prediction(result)

    def _now(self) -> datetime:
        value = self._clock()
        if not isinstance(value, datetime):
            raise TypeError("clock must return datetime")
        return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)


def _row_features(row: pd.Series) -> dict[str, Any]:
    return {str(key): value for key, value in row.items()}


def _row_datetime(row: pd.Series, column: str | None) -> datetime | None:
    if column is None or column not in row:
        return None
    value = row[column]
    if isinstance(value, pd.Timestamp):
        value = value.to_pydatetime()
    if isinstance(value, datetime):
        return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, str) and value.strip():
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.astimezone(UTC) if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    return None


def _row_text(row: pd.Series, column: str | None) -> str | None:
    if column is None or column not in row:
        return None
    value = row[column]
    if value is None or pd.isna(value):
        return None
    text = str(value)
    return text or None


def _jsonable(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, np.generic):
        return value.item()
    if pd.isna(value):
        return None
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [_jsonable(item) for item in value]
    return value

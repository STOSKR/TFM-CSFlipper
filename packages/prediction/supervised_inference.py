"""Inference-only loader for versioned supervised model artifacts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Protocol

import numpy as np
import pandas as pd  # type: ignore[import-untyped]


class SupervisedInferenceError(RuntimeError):
    """Raised when a versioned supervised model cannot be used for inference."""


class ProbabilisticModel(Protocol):
    def predict_proba(self, frame: pd.DataFrame) -> Any:
        """Return class probabilities for the given feature frame."""


@dataclass(frozen=True, slots=True)
class SupervisedPrediction:
    model_id: str
    probability: Decimal
    threshold: Decimal
    is_signal: bool
    prediction_name: str


@dataclass(frozen=True, slots=True)
class SupervisedModelMetadata:
    model_id: str
    model_file: str
    prediction_name: str
    target_column: str
    feature_columns: tuple[str, ...]
    decision_threshold: Decimal


@dataclass(frozen=True, slots=True)
class SupervisedModelArtifact:
    artifact_dir: Path
    metadata: SupervisedModelMetadata
    model: ProbabilisticModel

    @classmethod
    def load(cls, artifact_dir: Path) -> SupervisedModelArtifact:
        metadata = _load_metadata(artifact_dir / "metadata.json")
        model_path = artifact_dir / metadata.model_file
        if not model_path.exists():
            raise SupervisedInferenceError(f"model file not found: {model_path}")
        joblib = _joblib()
        model = joblib.load(model_path)
        if not hasattr(model, "predict_proba"):
            raise SupervisedInferenceError("model artifact does not expose predict_proba")
        return cls(
            artifact_dir=artifact_dir,
            metadata=metadata,
            model=model,
        )

    def predict_frame(self, frame: pd.DataFrame) -> tuple[SupervisedPrediction, ...]:
        features = self._feature_frame(frame)
        probabilities = np.asarray(self.model.predict_proba(features))
        if probabilities.ndim != 2 or probabilities.shape[1] < 2:
            raise SupervisedInferenceError("predict_proba must return a two-column matrix")
        return tuple(
            self._prediction_from_probability(float(probability))
            for probability in probabilities[:, 1]
        )

    def predict_one(self, features: dict[str, Any] | pd.Series) -> SupervisedPrediction:
        if isinstance(features, pd.Series):
            frame = features.to_frame().T
        else:
            frame = pd.DataFrame([features])
        return self.predict_frame(frame)[0]

    def _feature_frame(self, frame: pd.DataFrame) -> pd.DataFrame:
        missing = [
            column
            for column in self.metadata.feature_columns
            if column not in frame.columns
        ]
        if missing:
            raise SupervisedInferenceError(
                "missing supervised model features: " + ", ".join(missing)
            )
        return frame.loc[:, self.metadata.feature_columns]

    def _prediction_from_probability(self, probability: float) -> SupervisedPrediction:
        probability_decimal = Decimal(str(probability))
        return SupervisedPrediction(
            model_id=self.metadata.model_id,
            probability=probability_decimal,
            threshold=self.metadata.decision_threshold,
            is_signal=probability_decimal >= self.metadata.decision_threshold,
            prediction_name=self.metadata.prediction_name,
        )


def _load_metadata(path: Path) -> SupervisedModelMetadata:
    if not path.exists():
        raise SupervisedInferenceError(f"metadata file not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "supervised_model_artifact.v1":
        raise SupervisedInferenceError("unsupported supervised model metadata schema")
    feature_columns = payload.get("feature_columns")
    if not isinstance(feature_columns, list) or not all(
        isinstance(column, str) and column for column in feature_columns
    ):
        raise SupervisedInferenceError("metadata feature_columns must be a non-empty string list")
    return SupervisedModelMetadata(
        model_id=_required_str(payload, "model_id"),
        model_file=_required_str(payload, "model_file"),
        prediction_name=_required_str(payload, "prediction_name"),
        target_column=_required_str(payload, "target_column"),
        feature_columns=tuple(feature_columns),
        decision_threshold=Decimal(str(payload["decision_threshold"])),
    )


def _required_str(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise SupervisedInferenceError(f"metadata field must be a non-empty string: {key}")
    return value


def _joblib() -> Any:
    try:
        import joblib  # type: ignore[import-untyped]
    except ImportError as exc:
        raise SupervisedInferenceError("joblib is required to load supervised models") from exc
    return joblib

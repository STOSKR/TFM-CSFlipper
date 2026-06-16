import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd  # type: ignore[import-untyped]
import pytest

from packages.prediction.supervised_inference import SupervisedInferenceError
from packages.prediction.supervised_service import (
    SupervisedInferenceResult,
    SupervisedInferenceService,
)


class TinyProbabilityModel:
    def predict_proba(self, frame: pd.DataFrame) -> list[list[float]]:
        probabilities = []
        for _, row in frame.iterrows():
            probability = 0.9 if float(row["feature_a"]) > 1 else 0.4
            probabilities.append([1.0 - probability, probability])
        return probabilities


class MemorySink:
    def __init__(self) -> None:
        self.results: list[SupervisedInferenceResult] = []

    def record_supervised_prediction(self, result: SupervisedInferenceResult) -> None:
        self.results.append(result)


def test_supervised_service_scores_feature_snapshot_and_records_sink(
    tmp_path: Path,
) -> None:
    sink = MemorySink()
    service = SupervisedInferenceService.load(
        _artifact_dir(tmp_path),
        sink=sink,
        clock=lambda: datetime(2026, 6, 16, 10, 0, tzinfo=UTC),
    )

    result = service.score_features(
        {
            "feature_a": 2,
            "feature_b": "AK-47 | Slate",
            "extra": "ignored",
        },
        observed_at=datetime(2026, 6, 16, 9, 30, tzinfo=UTC),
        correlation_id="run-1",
    )

    assert result.model_id == "test-model"
    assert result.prediction_name == "direction_up_probability"
    assert str(result.probability) == "0.9"
    assert str(result.threshold) == "0.8"
    assert result.is_signal is True
    assert result.target_column == "is_up"
    assert result.scored_at == datetime(2026, 6, 16, 10, 0, tzinfo=UTC)
    assert result.observed_at == datetime(2026, 6, 16, 9, 30, tzinfo=UTC)
    assert result.correlation_id == "run-1"
    assert result.marl_feature_name == "direction_up_probability"
    assert result.feature_snapshot == {
        "feature_a": 2,
        "feature_b": "AK-47 | Slate",
    }
    assert sink.results == [result]


def test_supervised_service_scores_batch_with_trace_columns(tmp_path: Path) -> None:
    service = SupervisedInferenceService.load(
        _artifact_dir(tmp_path),
        clock=lambda: datetime(2026, 6, 16, 10, 0, tzinfo=UTC),
    )
    frame = pd.DataFrame(
        [
            {
                "feature_a": 1,
                "feature_b": "one",
                "observed_at": "2026-06-16T09:00:00+00:00",
                "correlation_id": "a",
            },
            {
                "feature_a": 2,
                "feature_b": "two",
                "observed_at": "2026-06-16T09:05:00+00:00",
                "correlation_id": "b",
            },
        ]
    )

    batch = service.score_frame(
        frame,
        observed_at_column="observed_at",
        correlation_id_column="correlation_id",
    )

    assert batch.model_id == "test-model"
    assert batch.scored_at == datetime(2026, 6, 16, 10, 0, tzinfo=UTC)
    assert [str(result.probability) for result in batch.results] == ["0.4", "0.9"]
    assert [result.is_signal for result in batch.results] == [False, True]
    assert [result.correlation_id for result in batch.results] == ["a", "b"]
    assert batch.results[0].observed_at == datetime(2026, 6, 16, 9, 0, tzinfo=UTC)


def test_supervised_service_rejects_missing_contract_features(tmp_path: Path) -> None:
    service = SupervisedInferenceService.load(_artifact_dir(tmp_path))

    with pytest.raises(SupervisedInferenceError, match="feature_b"):
        service.score_features({"feature_a": 1})


def _artifact_dir(tmp_path: Path) -> Path:
    artifact_dir = tmp_path / "artifact"
    artifact_dir.mkdir()
    _joblib().dump(TinyProbabilityModel(), artifact_dir / "calibrated_model.joblib")
    (artifact_dir / "metadata.json").write_text(
        json.dumps(
            {
                "schema_version": "supervised_model_artifact.v1",
                "model_id": "test-model",
                "model_file": "calibrated_model.joblib",
                "prediction_name": "direction_up_probability",
                "target_column": "is_up",
                "feature_columns": ["feature_a", "feature_b"],
                "decision_threshold": 0.8,
            }
        ),
        encoding="utf-8",
    )
    return artifact_dir


def _joblib() -> Any:
    import joblib  # type: ignore[import-untyped]

    return joblib

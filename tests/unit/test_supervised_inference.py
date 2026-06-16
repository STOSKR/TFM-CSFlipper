import json
from pathlib import Path
from typing import Any

import pandas as pd  # type: ignore[import-untyped]
import pytest

from packages.prediction.supervised_inference import (
    SupervisedInferenceError,
    SupervisedModelArtifact,
)


class TinyProbabilityModel:
    def predict_proba(self, frame: pd.DataFrame) -> list[list[float]]:
        return [[0.25, 0.75] for _ in range(len(frame))]


def test_supervised_artifact_loads_and_predicts_with_versioned_threshold(
    tmp_path: Path,
) -> None:
    artifact_dir = _artifact_dir(tmp_path)

    artifact = SupervisedModelArtifact.load(artifact_dir)
    prediction = artifact.predict_one({"feature_b": 2, "feature_a": 1, "extra": "ignored"})

    assert prediction.model_id == "test-model"
    assert prediction.prediction_name == "direction_up_probability"
    assert str(prediction.probability) == "0.75"
    assert str(prediction.threshold) == "0.7"
    assert prediction.is_signal is True


def test_supervised_artifact_predicts_multiple_rows(tmp_path: Path) -> None:
    artifact = SupervisedModelArtifact.load(_artifact_dir(tmp_path))

    predictions = artifact.predict_frame(
        pd.DataFrame(
            [
                {"feature_a": 1, "feature_b": 2},
                {"feature_a": 3, "feature_b": 4},
            ]
        )
    )

    assert len(predictions) == 2
    assert all(prediction.is_signal for prediction in predictions)


def test_supervised_artifact_rejects_missing_features(tmp_path: Path) -> None:
    artifact = SupervisedModelArtifact.load(_artifact_dir(tmp_path))

    with pytest.raises(SupervisedInferenceError, match="feature_b"):
        artifact.predict_one({"feature_a": 1})


def test_supervised_artifact_rejects_missing_model_file(tmp_path: Path) -> None:
    artifact_dir = _artifact_dir(tmp_path)
    (artifact_dir / "calibrated_model.joblib").unlink()

    with pytest.raises(SupervisedInferenceError, match="model file not found"):
        SupervisedModelArtifact.load(artifact_dir)


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
                "decision_threshold": 0.7,
            }
        ),
        encoding="utf-8",
    )
    return artifact_dir


def _joblib() -> Any:
    import joblib  # type: ignore[import-untyped]

    return joblib

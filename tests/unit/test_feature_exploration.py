import json
from pathlib import Path

import pandas as pd  # type: ignore[import-untyped]

from packages.datasets.feature_exploration import (
    FeatureExplorationConfig,
    explore_supervised_features,
)


def test_explore_supervised_features_reports_signal_and_recommendations(tmp_path: Path) -> None:
    dataset_dir = tmp_path / "dataset"
    dataset_dir.mkdir()
    _write_dataset(dataset_dir)

    report = explore_supervised_features(
        FeatureExplorationConfig(
            dataset_dir=dataset_dir,
            sample_rows_per_split=20,
            high_cardinality_threshold=3,
            redundancy_threshold=0.99,
        )
    )

    assert report["schema_version"] == "supervised_feature_exploration.v1"
    assert report["target_rate_by_split"]["train"] == 0.5
    assert report["numeric_features"][0]["feature"] == "signal"
    assert "signal" in report["recommendations"]["strong_univariate_numeric_features"]
    assert "category_high" in report["recommendations"]["high_cardinality_categoricals"]
    assert report["redundant_numeric_pairs"][0]["left"] == "signal"
    assert report["redundant_numeric_pairs"][0]["right"] == "signal_copy"
    assert (dataset_dir / "feature_exploration.json").exists()


def _write_dataset(dataset_dir: Path) -> None:
    metadata = {
        "target_column": "is_up",
        "feature_columns": ["signal", "signal_copy", "noise", "category_high", "bucket"],
        "numeric_features": ["signal", "signal_copy", "noise"],
        "categorical_features": ["category_high", "bucket"],
    }
    (dataset_dir / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    train = pd.DataFrame(
        {
            "signal": [0, 1, 2, 3, 4, 5],
            "signal_copy": [0, 1, 2, 3, 4, 5],
            "noise": [2, 2, 2, 2, 2, 2],
            "category_high": ["a", "b", "c", "d", "e", "f"],
            "bucket": ["low", "low", "low", "high", "high", "high"],
            "is_up": [0, 0, 0, 1, 1, 1],
        }
    )
    validation = train.assign(noise=[1, 1, 1, 1, 1, 1])
    test = train.assign(noise=[3, 3, 3, 3, 3, 3])
    train.to_parquet(dataset_dir / "train.parquet", index=False)
    validation.to_parquet(dataset_dir / "validation.parquet", index=False)
    test.to_parquet(dataset_dir / "test.parquet", index=False)

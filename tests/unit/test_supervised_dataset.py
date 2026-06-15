import json
from datetime import datetime
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from packages.datasets.supervised import (
    SupervisedDatasetBuildConfig,
    build_supervised_dataset,
    derived_supervised_feature_columns,
    supervised_feature_columns,
)


def test_build_supervised_dataset_writes_temporal_splits_and_metadata(tmp_path: Path) -> None:
    input_path = tmp_path / "engineered.parquet"
    output_dir = tmp_path / "dataset"
    _write_engineered_parquet(input_path)

    metadata = build_supervised_dataset(
        SupervisedDatasetBuildConfig(
            input_path=input_path,
            output_dir=output_dir,
            validation_start=datetime(2025, 1, 1),
            test_start=datetime(2026, 1, 1),
            batch_size=2,
        )
    )

    assert metadata["splits"]["train"]["rows"] == 2
    assert metadata["splits"]["validation"]["rows"] == 1
    assert metadata["splits"]["test"]["rows"] == 1
    assert metadata["splits"]["train"]["target_rate"] == 0.5
    assert "future_return" not in metadata["feature_columns"]
    assert "future_price_cents" not in metadata["feature_columns"]
    assert "is_safe" not in metadata["feature_columns"]
    assert "is_up" not in metadata["feature_columns"]
    assert "ret_7d" in metadata["feature_columns"]
    assert "primary_item_key" in metadata["categorical_features"]
    assert metadata["primary_group_column"] == "primary_item_key"
    assert "price_eur" in metadata["numeric_features"]
    assert "ret_7d_clipped" in metadata["numeric_features"]
    assert "log_turnover_eur" in metadata["numeric_features"]
    assert (output_dir / "train.parquet").exists()
    assert (output_dir / "validation.parquet").exists()
    assert (output_dir / "test.parquet").exists()
    assert (output_dir / "metadata.json").exists()
    assert (output_dir / "feature_profile.json").exists()

    persisted_metadata = json.loads((output_dir / "metadata.json").read_text(encoding="utf-8"))
    assert persisted_metadata["schema_version"] == "supervised_direction_dataset.v1"

    profile = json.loads((output_dir / "feature_profile.json").read_text(encoding="utf-8"))
    assert profile["schema_version"] == "feature_profile.v1"
    assert profile["numeric_features_ranked"]


def test_supervised_feature_columns_excludes_trace_and_leakage_columns() -> None:
    schema = pa.schema(
        [
            ("variant_id", pa.string()),
            ("ds", pa.timestamp("ms")),
            ("price_cents", pa.int32()),
            ("future_return", pa.float64()),
            ("is_safe", pa.int64()),
            ("is_up", pa.int64()),
            ("direction", pa.string()),
        ]
    )

    features = supervised_feature_columns(schema)

    assert features == ("price_cents",)


def test_derived_supervised_feature_columns_adds_primary_item_group() -> None:
    features = derived_supervised_feature_columns(
        (
            "item_key",
            "weapon_key",
            "skin_key",
            "collection",
            "rarity",
            "w",
            "st",
            "price_cents",
            "sales",
            "ret_7d",
            "sales_z_30d",
        )
    )

    assert "primary_item_key" in features
    assert "weapon_wear_key" in features
    assert "price_eur" in features
    assert "turnover_eur" in features
    assert "ret_7d_clipped" in features
    assert "sales_z_30d_clipped" in features


def test_build_supervised_dataset_can_filter_to_recent_window(tmp_path: Path) -> None:
    input_path = tmp_path / "engineered.parquet"
    output_dir = tmp_path / "dataset"
    _write_engineered_parquet(input_path)

    metadata = build_supervised_dataset(
        SupervisedDatasetBuildConfig(
            input_path=input_path,
            output_dir=output_dir,
            start_date=datetime(2025, 1, 1),
            validation_start=datetime(2026, 1, 1),
            test_start=datetime(2026, 2, 1),
            batch_size=2,
        )
    )

    assert metadata["source_rows"] == 4
    assert metadata["rows_included"] == 2
    assert metadata["split_policy"]["start"] == "ds >= 2025-01-01"
    assert metadata["splits"]["train"]["rows"] == 1
    assert metadata["splits"]["validation"]["rows"] == 0
    assert metadata["splits"]["test"]["rows"] == 1

    train = pq.read_table(output_dir / "train.parquet").to_pandas()  # type: ignore[no-untyped-call]
    assert train["primary_item_key"].tolist() == ["item-b__FT__0"]
    assert train["price_eur"].tolist() == [0.9]
    assert train["ret_7d_clipped"].tolist() == [0.3]

    profile = json.loads((output_dir / "feature_profile.json").read_text(encoding="utf-8"))
    assert profile["rows_observed"] == 2


def _write_engineered_parquet(path: Path) -> None:
    table = pa.table(
        {
            "variant_id": ["a", "a", "b", "b"],
            "item_key": ["item-a", "item-a", "item-b", "item-b"],
            "unique_id": ["a-1", "a-2", "b-1", "b-2"],
            "ds": [
                datetime(2024, 1, 1),
                datetime(2024, 6, 1),
                datetime(2025, 6, 1),
                datetime(2026, 2, 1),
            ],
            "day": [1, 2, 3, 4],
            "category": ["rifle", "rifle", "pistol", "pistol"],
            "weapon_key": ["ak_47", "ak_47", "p250", "p250"],
            "skin_key": ["slate", "slate", "sand_dune", "sand_dune"],
            "collection": ["snakebite", "snakebite", "dust_2", "dust_2"],
            "rarity": ["restricted", "restricted", "consumer_grade", "consumer_grade"],
            "w": ["FT", "FT", "FT", "FN"],
            "st": [1, 1, 0, 0],
            "price_cents": [100, 120, 90, 150],
            "ret_7d": [0.1, -0.2, 0.3, 0.4],
            "sales": [10, 11, 12, 13],
            "future_price_cents": [120, 90, 150, 160],
            "future_return": [0.2, -0.25, 0.66, 0.06],
            "direction": ["up", "down", "up", "up"],
            "is_safe": [1, 0, 1, 1],
            "y": [0.2, -0.25, 0.66, 0.06],
            "y_7d_direction": ["up", "down", "up", "up"],
            "is_up": [1, 0, 1, 1],
        }
    )
    pq.write_table(table, path, row_group_size=2)  # type: ignore[no-untyped-call]

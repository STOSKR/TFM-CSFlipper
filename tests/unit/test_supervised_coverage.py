from datetime import datetime
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from packages.datasets.supervised_coverage import (
    SupervisedCoverageConfig,
    analyze_supervised_coverage,
)


def test_analyze_supervised_coverage_reports_variant_overlap(tmp_path: Path) -> None:
    dataset_dir = tmp_path / "dataset"
    dataset_dir.mkdir()
    (dataset_dir / "metadata.json").write_text(
        """
        {
          "date_column": "ds",
          "target_column": "is_up"
        }
        """,
        encoding="utf-8",
    )
    _write_split(dataset_dir / "train.parquet", ["a", "a", "b"], [1, 0, 1], 2024)
    _write_split(dataset_dir / "validation.parquet", ["a", "c"], [1, 0], 2025)
    _write_split(dataset_dir / "test.parquet", ["a", "b"], [0, 1], 2026)

    report = analyze_supervised_coverage(
        SupervisedCoverageConfig(
            dataset_dir=dataset_dir,
            batch_size=2,
            min_train_rows_per_variant=2,
        )
    )

    assert report["schema_version"] == "supervised_coverage.v1"
    assert report["splits"]["train"]["rows"] == 3
    assert report["splits"]["train"]["variants"] == 2
    assert report["splits"]["train"]["variants_below_min_train_rows"] == 1
    assert report["cross_split"]["variants_in_all_splits"] == 1
    assert report["cross_split"]["validation_variants_missing_from_train"] == 1
    assert (dataset_dir / "coverage_report.json").exists()


def _write_split(path: Path, variants: list[str], targets: list[int], year: int) -> None:
    table = pa.table(
        {
            "variant_id": variants,
            "item_key": [f"item-{variant}" for variant in variants],
            "ds": [datetime(year, index + 1, 1) for index in range(len(variants))],
            "is_up": targets,
        }
    )
    pq.write_table(table, path, row_group_size=2)  # type: ignore[no-untyped-call]

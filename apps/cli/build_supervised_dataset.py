"""Build versioned supervised train/validation/test parquet splits."""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from packages.datasets.supervised import (
    DEFAULT_TEST_START,
    DEFAULT_VALIDATION_START,
    SupervisedDatasetBuildConfig,
    build_supervised_dataset,
)


def run(args: argparse.Namespace) -> int:
    metadata = build_supervised_dataset(
        SupervisedDatasetBuildConfig(
            input_path=args.input,
            output_dir=args.output,
            validation_start=args.validation_start,
            test_start=args.test_start,
            batch_size=args.batch_size,
        )
    )
    print(f"dataset_dir={metadata['output_dir']}")
    print(f"source_rows={metadata['source_rows']}")
    for split_name, split in metadata["splits"].items():
        print(
            f"split={split_name} rows={split['rows']} "
            f"target_rate={split['target_rate']} "
            f"min_date={split['min_date']} max_date={split['max_date']}"
        )
    print(f"features={len(metadata['feature_columns'])}")
    print("metadata=metadata.json")
    print("feature_profile=feature_profile.json")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build supervised ML parquet splits from the engineered history dataset."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/direction_dataset_engineered.parquet"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/datasets/supervised_direction_v1"),
    )
    parser.add_argument(
        "--validation-start",
        type=_date_arg,
        default=DEFAULT_VALIDATION_START,
    )
    parser.add_argument("--test-start", type=_date_arg, default=DEFAULT_TEST_START)
    parser.add_argument("--batch-size", type=int, default=65_536)
    args = parser.parse_args()
    raise SystemExit(run(args))


def _date_arg(value: str) -> datetime:
    return datetime.fromisoformat(value)


if __name__ == "__main__":
    main()

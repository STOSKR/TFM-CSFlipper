"""Analyze supervised dataset coverage before model training."""

from __future__ import annotations

import argparse
from pathlib import Path

from packages.datasets.supervised_coverage import (
    SupervisedCoverageConfig,
    analyze_supervised_coverage,
)


def run(args: argparse.Namespace) -> int:
    report = analyze_supervised_coverage(
        SupervisedCoverageConfig(
            dataset_dir=args.dataset_dir,
            output_path=args.output,
            batch_size=args.batch_size,
            min_train_rows_per_variant=args.min_train_rows_per_variant,
        )
    )
    print(f"dataset_dir={report['dataset_dir']}")
    print(f"output={args.output or args.dataset_dir / 'coverage_report.json'}")
    for split_name, split in report["splits"].items():
        rows_per_variant = split["rows_per_variant"]
        print(
            f"split={split_name} rows={split['rows']} variants={split['variants']} "
            f"target_rate={split['target_rate']} "
            f"rows_p10={rows_per_variant.get('p10')} rows_p50={rows_per_variant.get('p50')} "
            f"rows_p90={rows_per_variant.get('p90')}"
        )
    cross_split = report["cross_split"]
    print(
        "cross_split="
        f"all={cross_split['variants_in_all_splits']} "
        f"val_unseen={cross_split['validation_variants_missing_from_train']} "
        f"test_unseen={cross_split['test_variants_missing_from_train']}"
    )
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyze variant/date coverage across supervised parquet splits."
    )
    parser.add_argument(
        "--dataset-dir",
        type=Path,
        default=Path("data/datasets/supervised_direction_v1"),
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--batch-size", type=int, default=65_536)
    parser.add_argument("--min-train-rows-per-variant", type=int, default=90)
    args = parser.parse_args()
    raise SystemExit(run(args))


if __name__ == "__main__":
    main()

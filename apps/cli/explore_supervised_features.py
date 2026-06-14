"""Explore supervised dataset features before model training."""

from __future__ import annotations

import argparse
from pathlib import Path

from packages.datasets.feature_exploration import (
    FeatureExplorationConfig,
    explore_supervised_features,
)


def run(args: argparse.Namespace) -> int:
    report = explore_supervised_features(
        FeatureExplorationConfig(
            dataset_dir=args.dataset_dir,
            output_path=args.output,
            sample_rows_per_split=args.sample_rows_per_split,
            batch_size=args.batch_size,
        )
    )
    recommendations = report["recommendations"]
    print(f"dataset_dir={report['dataset_dir']}")
    print(f"output={args.output or args.dataset_dir / 'feature_exploration.json'}")
    print(f"sample_rows={report['sample_rows_per_split']}")
    print(f"target_rate_by_split={report['target_rate_by_split']}")
    print(
        "strong_numeric="
        f"{','.join(recommendations['strong_univariate_numeric_features'][:12]) or '-'}"
    )
    print(
        "high_cardinality_categoricals="
        f"{','.join(recommendations['high_cardinality_categoricals']) or '-'}"
    )
    print(f"leakage_suspects={','.join(recommendations['leakage_suspects']) or '-'}")
    print(
        "redundant_drop_candidates="
        f"{','.join(recommendations['redundant_numeric_drop_candidates'][:12]) or '-'}"
    )
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create feature exploration and engineering recommendations."
    )
    parser.add_argument(
        "--dataset-dir",
        type=Path,
        default=Path("data/datasets/supervised_direction_v1"),
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--sample-rows-per-split", type=int, default=200_000)
    parser.add_argument("--batch-size", type=int, default=65_536)
    args = parser.parse_args()
    raise SystemExit(run(args))


if __name__ == "__main__":
    main()

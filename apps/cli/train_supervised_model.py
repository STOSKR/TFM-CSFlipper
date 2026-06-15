"""Train supervised model candidates on the versioned direction dataset."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

from packages.prediction.supervised_training import (
    SupervisedTrainingConfig,
    train_supervised_models,
)


def run(args: argparse.Namespace) -> int:
    output_dir = args.output_dir or _default_output_dir()
    report = train_supervised_models(
        SupervisedTrainingConfig(
            dataset_dir=args.dataset_dir,
            output_dir=output_dir,
            max_train_rows=args.max_train_rows,
            max_validation_rows=args.max_validation_rows,
            max_test_rows=args.max_test_rows,
            batch_size=args.batch_size,
            cv_splits=args.cv_splits,
            calibration_method=args.calibration_method,
            models=tuple(args.models),
            exclude_features=tuple(args.exclude_features),
            exclude_feature_suffixes=tuple(args.exclude_feature_suffixes),
            selection_metric=args.selection_metric,
            selection_threshold=args.selection_threshold,
            min_selection_signals=args.min_selection_signals,
        )
    )
    print(f"output_dir={report['output_dir']}")
    print(f"model_path={report['model_path']}")
    print(f"selected_candidate={report['selected_candidate']}")
    print(f"validation={report['calibration']['validation']}")
    print(f"test={report['calibration']['test']}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Train and calibrate supervised model candidates."
    )
    parser.add_argument(
        "--dataset-dir",
        type=Path,
        default=Path("data/datasets/supervised_direction_v1"),
    )
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--max-train-rows", type=int, default=200_000)
    parser.add_argument("--max-validation-rows", type=int, default=100_000)
    parser.add_argument("--max-test-rows", type=int, default=100_000)
    parser.add_argument("--batch-size", type=int, default=65_536)
    parser.add_argument("--cv-splits", type=int, default=3)
    parser.add_argument(
        "--calibration-method",
        choices=("isotonic", "sigmoid"),
        default="isotonic",
    )
    parser.add_argument(
        "--models",
        nargs="+",
        choices=("dummy", "logistic", "random_forest", "hist_gradient_boosting"),
        default=("dummy", "logistic", "random_forest", "hist_gradient_boosting"),
    )
    parser.add_argument(
        "--exclude-features",
        nargs="*",
        default=(),
        help="Exact feature names to drop from training while still loading trace columns.",
    )
    parser.add_argument(
        "--exclude-feature-suffixes",
        nargs="*",
        default=(),
        help="Drop every training feature ending with one of these suffixes.",
    )
    parser.add_argument(
        "--selection-metric",
        choices=("roc_auc", "average_precision", "precision_at_threshold"),
        default="roc_auc",
    )
    parser.add_argument("--selection-threshold", type=float, default=0.8)
    parser.add_argument("--min-selection-signals", type=int, default=50)
    args = parser.parse_args()
    raise SystemExit(run(args))


def _default_output_dir() -> Path:
    run_id = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S")
    return Path("model-runs") / "supervised_direction_v1" / run_id


if __name__ == "__main__":
    main()

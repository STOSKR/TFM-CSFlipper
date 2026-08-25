"""Build the trading dataset and train a supervised model in one cron-friendly command."""

from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

from apps.cli.build_trading_dataset import run as build_dataset
from apps.cli.train_supervised_model import run as train_model


def run(args: argparse.Namespace) -> int:
    now = datetime.now(tz=UTC)
    validation_start = args.validation_start or _midnight_utc(now - timedelta(days=60))
    test_start = args.test_start or _midnight_utc(now - timedelta(days=30))
    dataset_dir = args.dataset_dir
    model_output_dir = args.model_output_dir or _default_model_output_dir(now)

    build_code = asyncio.run(build_dataset(_dataset_args(args, validation_start, test_start)))
    if build_code != 0:
        return build_code
    return train_model(_training_args(args, dataset_dir, model_output_dir))


def _dataset_args(
    args: argparse.Namespace,
    validation_start: datetime,
    test_start: datetime,
) -> argparse.Namespace:
    return argparse.Namespace(
        config=args.config,
        input_parquet=None,
        output=args.dataset_dir,
        trade_direction=args.trade_direction,
        horizon_days=args.horizon_days,
        future_tolerance_days=args.future_tolerance_days,
        min_profit_eur=args.min_profit_eur,
        min_return=args.min_return,
        cny_per_eur=args.cny_per_eur,
        buff_sale_factor=args.buff_sale_factor,
        start_date=args.start_date,
        validation_start=validation_start,
        test_start=test_start,
        query_start=args.query_start,
        limit_rows=args.limit_rows,
    )


def _training_args(
    args: argparse.Namespace,
    dataset_dir: Path,
    model_output_dir: Path,
) -> argparse.Namespace:
    return argparse.Namespace(
        dataset_dir=dataset_dir,
        output_dir=model_output_dir,
        max_train_rows=args.max_train_rows,
        max_validation_rows=args.max_validation_rows,
        max_test_rows=args.max_test_rows,
        batch_size=args.batch_size,
        cv_splits=args.cv_splits,
        calibration_method=args.calibration_method,
        models=tuple(args.models),
        exclude_features=(),
        exclude_feature_suffixes=(),
        include_group_identity_features=False,
        selection_metric=args.selection_metric,
        selection_threshold=args.selection_threshold,
        min_selection_signals=args.min_selection_signals,
    )


def _default_model_output_dir(now: datetime) -> Path:
    run_id = now.strftime("%Y%m%d_%H%M%S")
    return Path("model-runs") / "trading_profit_v2" / run_id


def _midnight_utc(value: datetime) -> datetime:
    return value.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Rebuild trading features and train a supervised model."
    )
    parser.add_argument("--config", type=Path, default=Path("csflipper_config.toml"))
    parser.add_argument("--dataset-dir", type=Path, default=Path("data/datasets/trading_profit_v2"))
    parser.add_argument("--model-output-dir", type=Path)
    parser.add_argument(
        "--trade-direction",
        choices=("buff_to_steam_sell", "steam_to_buff_buy_order"),
        default="buff_to_steam_sell",
    )
    parser.add_argument("--horizon-days", type=int, default=8)
    parser.add_argument("--future-tolerance-days", type=int, default=7)
    parser.add_argument("--min-profit-eur", type=str, default="0")
    parser.add_argument("--min-return", type=str, default="0.10")
    parser.add_argument("--cny-per-eur", type=str, default="8")
    parser.add_argument("--buff-sale-factor", type=str, default="0.975")
    parser.add_argument("--start-date", type=_date_arg)
    parser.add_argument("--query-start", type=_date_arg)
    parser.add_argument("--validation-start", type=_date_arg)
    parser.add_argument("--test-start", type=_date_arg)
    parser.add_argument("--limit-rows", type=int)
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
        "--selection-metric",
        choices=("roc_auc", "average_precision", "precision_at_threshold"),
        default="precision_at_threshold",
    )
    parser.add_argument("--selection-threshold", type=float, default=0.8)
    parser.add_argument("--min-selection-signals", type=int, default=50)
    args = parser.parse_args()
    raise SystemExit(run(args))


def _date_arg(value: str) -> datetime:
    return datetime.fromisoformat(value)


if __name__ == "__main__":
    main()

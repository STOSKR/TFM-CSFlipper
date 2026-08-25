import argparse
from datetime import UTC, datetime
from pathlib import Path

from apps.cli.retrain_trading_model import (
    _dataset_args,
    _default_model_output_dir,
    _midnight_utc,
    _training_args,
)


def test_retrain_trading_model_builds_dataset_and_training_args() -> None:
    args = argparse.Namespace(
        config=Path("csflipper_config.toml"),
        dataset_dir=Path("data/datasets/trading_profit_v1"),
        trade_direction="steam_to_buff_buy_order",
        horizon_days=8,
        future_tolerance_days=7,
        min_profit_eur="0",
        min_return="0",
        cny_per_eur="8",
        buff_sale_factor="0.975",
        start_date=None,
        query_start=datetime(2025, 6, 16, tzinfo=UTC),
        limit_rows=None,
        max_train_rows=200_000,
        max_validation_rows=100_000,
        max_test_rows=100_000,
        batch_size=65_536,
        cv_splits=3,
        calibration_method="isotonic",
        models=("logistic",),
        selection_metric="precision_at_threshold",
        selection_threshold=0.8,
        min_selection_signals=50,
    )
    validation_start = datetime(2026, 5, 1, tzinfo=UTC)
    test_start = datetime(2026, 6, 1, tzinfo=UTC)
    model_output_dir = Path("model-runs/trading_profit_v1/20260706_010203")

    dataset_args = _dataset_args(args, validation_start, test_start)
    training_args = _training_args(args, args.dataset_dir, model_output_dir)

    assert dataset_args.output == Path("data/datasets/trading_profit_v1")
    assert dataset_args.validation_start == validation_start
    assert dataset_args.test_start == test_start
    assert dataset_args.query_start == datetime(2025, 6, 16, tzinfo=UTC)
    assert training_args.dataset_dir == Path("data/datasets/trading_profit_v1")
    assert training_args.output_dir == model_output_dir
    assert training_args.models == ("logistic",)


def test_retrain_trading_model_defaults_use_timestamped_model_run() -> None:
    now = datetime(2026, 7, 6, 1, 2, 3, tzinfo=UTC)

    assert _default_model_output_dir(now) == Path(
        "model-runs/trading_profit_v2/20260706_010203"
    )
    assert _midnight_utc(now) == datetime(2026, 7, 6, tzinfo=UTC)

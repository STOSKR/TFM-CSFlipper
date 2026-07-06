from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pandas as pd  # type: ignore[import-untyped]
import pyarrow.parquet as pq

from packages.datasets.trading import (
    TradingDatasetBuildConfig,
    build_trading_dataset_from_history,
    trading_examples_from_history,
)


def test_trading_examples_create_profit_target_from_future_steam_sale() -> None:
    history = _history_frame()

    examples = trading_examples_from_history(
        history,
        config=TradingDatasetBuildConfig(
            output_dir=Path("-"),
            horizon_days=8,
            min_profit_eur=Decimal("0.50"),
            min_return=Decimal("0.05"),
            validation_start=datetime(2026, 1, 1),
            test_start=datetime(2026, 3, 1),
        ),
    )

    first = examples.iloc[0]
    assert first["buy_platform"] == "BUFF"
    assert first["buy_price_type"] == "listing"
    assert first["sell_platform"] == "STEAM"
    assert first["sell_price_type"] == "listing"
    assert first["cash_destination"] == "reinvest"
    assert first["buff_sell_price_eur"] == 10.0
    assert first["day_of_week"] == 0
    assert first["month"] == 12
    assert first["is_weekend"] == 0
    assert pd.isna(first["steam_sell_price_eur_lag_1d"])
    assert round(first["current_cash_value_eur"], 3) == 8.352
    assert first["future_steam_sell_price_eur"] == 13.0
    assert first["future_steam_net_sale_eur"] == 11.31
    assert round(first["future_profit_eur"], 2) == 1.31
    assert round(first["future_cash_profit_eur"], 3) == -0.952
    assert first["is_profitable"] == 1


def test_build_trading_dataset_writes_splits_and_metadata(tmp_path: Path) -> None:
    output_dir = tmp_path / "trading"

    metadata = build_trading_dataset_from_history(
        _history_frame(),
        config=TradingDatasetBuildConfig(
            output_dir=output_dir,
            horizon_days=8,
            min_profit_eur=Decimal("0.50"),
            min_return=Decimal("0.05"),
            validation_start=datetime(2026, 1, 1),
            test_start=datetime(2026, 3, 1),
        ),
    )

    assert metadata["schema_version"] == "trading_supervised_dataset.v1"
    assert metadata["target_column"] == "is_profitable"
    assert metadata["primary_group_column"] == "representation_name"
    assert metadata["route_columns"] == [
        "buy_platform",
        "buy_price_type",
        "sell_platform",
        "sell_price_type",
        "cash_destination",
    ]
    assert "current_profit_eur" in metadata["numeric_features"]
    assert "is_weekend" in metadata["numeric_features"]
    assert "buy_platform" not in metadata["feature_columns"]
    assert "representation_name" not in metadata["feature_columns"]
    assert metadata["splits"]["train"]["rows"] == 1
    assert metadata["splits"]["validation"]["rows"] == 0
    assert metadata["splits"]["test"]["rows"] == 0
    assert (output_dir / "metadata.json").exists()

    train = pq.read_table(output_dir / "train.parquet").to_pandas()  # type: ignore[no-untyped-call]
    assert train["is_profitable"].tolist() == [1]
    assert train["buy_platform"].tolist() == ["BUFF"]
    assert train["sell_platform"].tolist() == ["STEAM"]
    assert train["steam_buff_spread_eur"].tolist() == [2.0]


def test_build_trading_dataset_drops_all_null_features(tmp_path: Path) -> None:
    history = _history_frame(include_sales_count=False)

    metadata = build_trading_dataset_from_history(
        history,
        config=TradingDatasetBuildConfig(
            output_dir=tmp_path / "trading",
            horizon_days=8,
            validation_start=datetime(2026, 1, 1),
            test_start=datetime(2026, 3, 1),
        ),
    )

    assert "steam_sales_count" not in metadata["feature_columns"]
    assert "steam_sales_count_lag_1d" not in metadata["feature_columns"]


def test_trading_examples_add_lag_and_rolling_features_without_future_leakage() -> None:
    history = _history_frame(
        (
            ("2025-12-01", 12.0, 10.0),
            ("2025-12-02", 14.0, 11.0),
            ("2025-12-03", 16.0, 12.0),
            ("2025-12-04", 18.0, 13.0),
        )
    )

    examples = trading_examples_from_history(
        history,
        config=TradingDatasetBuildConfig(
            output_dir=Path("-"),
            horizon_days=1,
            future_tolerance_days=0,
            validation_start=datetime(2026, 1, 1),
            test_start=datetime(2026, 3, 1),
        ),
    )

    first = examples.iloc[0]
    assert first["steam_sell_price_eur"] == 12.0
    assert pd.isna(first["steam_sell_price_eur_lag_1d"])
    assert pd.isna(first["steam_sell_price_eur_rolling_mean_7d"])

    second = examples.iloc[1]
    assert second["steam_sell_price_eur"] == 14.0
    assert second["steam_sell_price_eur_lag_1d"] == 12.0
    assert second["steam_sell_price_eur_change_1d"] == 2.0
    assert round(second["steam_sell_price_eur_return_1d"], 3) == 0.167

    third = examples.iloc[2]
    assert third["steam_sell_price_eur_rolling_mean_7d"] == 13.0


def test_trading_examples_support_steam_to_buff_buy_order_direction() -> None:
    history = _history_frame()

    examples = trading_examples_from_history(
        history,
        config=TradingDatasetBuildConfig(
            output_dir=Path("-"),
            trade_direction="steam_to_buff_buy_order",
            horizon_days=8,
            min_profit_eur=Decimal("0"),
            min_return=Decimal("0"),
            validation_start=datetime(2026, 1, 1),
            test_start=datetime(2026, 3, 1),
        ),
    )

    first = examples.iloc[0]
    assert first["buy_platform"] == "STEAM"
    assert first["buy_price_type"] == "listing"
    assert first["sell_platform"] == "BUFF"
    assert first["sell_price_type"] == "buy_order"
    assert first["buy_price_eur"] == 12.0
    assert first["current_cash_value_eur"] == 9.2625
    assert first["future_buff_buy_order_price_eur"] == 10.0
    assert first["future_exit_net_eur"] == 9.75
    assert first["future_cash_value_eur"] == 9.75
    assert first["future_profit_eur"] == -2.25
    assert first["is_profitable"] == 0


def _history_frame(
    prices: tuple[tuple[str, float, float], ...] = (
        ("2025-12-01", 12.0, 10.0),
        ("2025-12-09", 13.0, 10.5),
    ),
    *,
    include_sales_count: bool = True,
) -> pd.DataFrame:
    rows = []
    for day, steam_price, buff_price in prices:
        rows.extend(
            [
                _row(day, "steam", "sell_price", steam_price, steam_price),
                _row(day, "buff163", "sell_price", buff_price, buff_price),
                _row(day, "buff163", "buy_order_price", buff_price - 0.5, buff_price - 0.5),
                _row(day, "buff163", "listing_count", 7, None),
            ]
        )
        if include_sales_count:
            rows.append(_row(day, "steam", "sales_count", 24, None))
    return pd.DataFrame(rows)


def _row(
    day: str,
    platform_id: str,
    metric_name: str,
    metric_value: float,
    price_eur: float | None,
) -> dict[str, object]:
    return {
        "item_id": "item-1",
        "representation_name": "AK-47 | Slate_FT_1",
        "name": "AK-47 | Slate",
        "quality": "Field-Tested",
        "stattrak": True,
        "observed_at": f"{day}T10:00:00+00:00",
        "platform_id": platform_id,
        "metric_name": metric_name,
        "metric_value": metric_value,
        "price_eur": price_eur,
        "price_cny": None,
    }

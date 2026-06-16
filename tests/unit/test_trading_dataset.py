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
    assert first["buff_sell_price_eur"] == 10.0
    assert first["future_steam_sell_price_eur"] == 13.0
    assert first["future_steam_net_sale_eur"] == 11.31
    assert round(first["future_profit_eur"], 2) == 1.31
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
    assert "current_profit_eur" in metadata["numeric_features"]
    assert "representation_name" not in metadata["feature_columns"]
    assert metadata["splits"]["train"]["rows"] == 1
    assert metadata["splits"]["validation"]["rows"] == 0
    assert metadata["splits"]["test"]["rows"] == 0
    assert (output_dir / "metadata.json").exists()

    train = pq.read_table(output_dir / "train.parquet").to_pandas()  # type: ignore[no-untyped-call]
    assert train["is_profitable"].tolist() == [1]
    assert train["steam_buff_spread_eur"].tolist() == [2.0]


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
    assert first["buy_price_eur"] == 12.0
    assert first["future_buff_buy_order_price_eur"] == 10.0
    assert first["future_exit_net_eur"] == 9.75
    assert first["future_profit_eur"] == -2.25
    assert first["is_profitable"] == 0


def _history_frame() -> pd.DataFrame:
    rows = []
    for day, steam_price, buff_price in (
        ("2025-12-01", 12.0, 10.0),
        ("2025-12-09", 13.0, 10.5),
    ):
        rows.extend(
            [
                _row(day, "steam", "sell_price", steam_price, steam_price),
                _row(day, "steam", "sales_count", 24, None),
                _row(day, "buff163", "sell_price", buff_price, buff_price),
                _row(day, "buff163", "buy_order_price", buff_price - 0.5, buff_price - 0.5),
                _row(day, "buff163", "listing_count", 7, None),
            ]
        )
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

import json
from decimal import Decimal
from pathlib import Path

import pandas as pd  # type: ignore[import-untyped]

from packages.marl import (
    MarketMARLEnvironment,
    load_market_episode_steps,
    select_price_stratified_item_ids,
)


def test_load_market_episode_steps_from_dataset_split(tmp_path: Path) -> None:
    dataset_dir = tmp_path / "dataset"
    dataset_dir.mkdir()
    pd.DataFrame(
        [
            {
                "item_id": "item-2",
                "representation_name": "M4A1-S | Nitro_MW_0",
                "observed_day": "2026-01-02",
                "buy_price_eur": 20.0,
                "current_exit_net_eur": 19.0,
                "current_return": -0.05,
                "current_cash_value_eur": 19.0,
                "current_cash_return": -0.05,
                "steam_sell_price_eur": 21.84,
                "buff_buy_order_price_eur": 19.0,
            },
            {
                "item_id": "item-1",
                "representation_name": "AK-47 | Slate_FT_0",
                "observed_day": "2026-01-01",
                "buy_price_eur": 10.0,
                "current_exit_net_eur": 12.0,
                "current_return": 0.2,
                "current_cash_value_eur": 12.0,
                "current_cash_return": 0.2,
                "steam_sell_price_eur": 13.79,
                "buff_buy_order_price_eur": 12.0,
            },
        ]
    ).to_parquet(dataset_dir / "train.parquet", index=False)
    (dataset_dir / "metadata.json").write_text(
        json.dumps({"trade_direction": "steam_to_buff_buy_order"}),
        encoding="utf-8",
    )

    steps = load_market_episode_steps(dataset_dir, split="train")

    assert [step.item_id for step in steps] == ["item-1", "item-2"]
    assert steps[0].buy_price_eur == Decimal("10.0")
    assert steps[0].buy_platform == "STEAM"
    assert steps[0].buy_price_type == "listing"
    assert steps[0].sell_platform == "BUFF"
    assert steps[0].sell_price_type == "buy_order"
    assert steps[0].cash_destination == "reinvest"
    assert steps[0].current_cash_value_eur == Decimal("12.0")
    assert steps[0].current_cash_return == Decimal("0.2")

    env = MarketMARLEnvironment(steps, initial_cash_eur=Decimal("100"))
    env.reset()
    _observations, rewards, terminations, _truncations, infos = env.step(
        {"scout": 1, "trader": 1, "portfolio": 1}
    )

    assert rewards["trader"] == 0.0
    assert terminations["portfolio"] is False
    assert infos["scout"]["executed_trade"] is True
    assert infos["scout"]["sell_platform"] == "BUFF"
    assert infos["scout"]["sell_price_type"] == "buy_order"
    assert infos["scout"]["cashflow"]["effective_cash_return"] == 0.2


def test_load_market_episode_steps_respects_limit(tmp_path: Path) -> None:
    path = tmp_path / "episode.parquet"
    pd.DataFrame(
        [
            {
                "item_id": f"item-{index}",
                "representation_name": f"Item {index}",
                "observed_day": f"2026-01-0{index + 1}",
                "buy_price_eur": 10 + index,
                "current_exit_net_eur": 11 + index,
                "current_return": 0.1,
            }
            for index in range(3)
        ]
    ).to_parquet(path, index=False)

    steps = load_market_episode_steps(path, limit=2)

    assert len(steps) == 2


def test_price_stratified_scenario_selects_shared_affordable_assets(tmp_path: Path) -> None:
    dataset_dir = tmp_path / "dataset"
    dataset_dir.mkdir()
    rows = [
        {
            "item_id": f"item-{index}",
            "representation_name": f"Item {index}",
            "observed_day": "2026-01-01",
            "buy_price_eur": price,
            "current_exit_net_eur": price,
            "current_return": 0.0,
        }
        for index, price in enumerate((5.0, 15.0, 45.0, 90.0), start=1)
    ]
    pd.DataFrame(rows).to_parquet(dataset_dir / "train.parquet", index=False)
    pd.DataFrame(rows[:-1]).to_parquet(dataset_dir / "validation.parquet", index=False)

    selected = select_price_stratified_item_ids(
        dataset_dir,
        asset_count=2,
        maximum_item_price_eur=50.0,
    )

    assert selected == ("item-1", "item-3")
    steps = load_market_episode_steps(dataset_dir, item_ids=frozenset(selected))
    assert [step.item_id for step in steps] == ["item-1", "item-3"]

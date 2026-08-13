import argparse

from apps.cli.run_marl_episode import run


def test_run_marl_episode_demo_buys_positive_route_only() -> None:
    result = run(
        argparse.Namespace(
            dataset_dir=None,
            split="train",
            limit=5,
            cash=100.0,
            policy="buy-positive",
            supervised_probability=True,
        )
    )

    assert result["steps"] == 2
    assert result["cash_available_eur"] == 79.0
    assert result["positions"][0]["item_id"] == "buff-to-steam"
    assert result["positions"][0]["buy_platform"] == "BUFF"
    assert result["positions"][0]["sold_at"] is None
    first_step = result["trace"][1]
    assert first_step["actions"] == {"scout": 1, "trader": 1, "portfolio": 1}
    assert first_step["infos"]["trader"]["buy_platform"] == "BUFF"
    assert first_step["infos"]["trader"]["buy_price_type"] == "listing"
    assert first_step["infos"]["trader"]["sell_platform"] == "STEAM"
    assert first_step["infos"]["trader"]["supervised_probability_enabled"] is True


def test_run_marl_episode_demo_can_buy_then_sell_after_unlock() -> None:
    result = run(
        argparse.Namespace(
            dataset_dir=None,
            split="train",
            limit=5,
            cash=100.0,
            policy="buy-and-sell",
            supervised_probability=True,
        )
    )

    assert result["cash_available_eur"] == 102.18
    assert result["portfolio"]["realized_profit_eur"] == 2.18
    assert result["portfolio"]["closed_positions"] == 1
    assert result["positions"][0]["sold_at"] == "2026-01-09"
    assert result["trace"][2]["actions"] == {"scout": 0, "trader": 2, "portfolio": 1}
    assert result["trace"][2]["infos"]["trader"]["executed_sale"] is True


def test_run_marl_episode_hold_policy_does_not_buy() -> None:
    result = run(
        argparse.Namespace(
            dataset_dir=None,
            split="train",
            limit=5,
            cash=100.0,
            policy="hold",
            supervised_probability=True,
        )
    )

    assert result["positions"] == []
    assert result["cash_available_eur"] == 100.0


def test_run_marl_episode_can_disable_supervised_probability_feature() -> None:
    result = run(
        argparse.Namespace(
            dataset_dir=None,
            split="train",
            limit=5,
            cash=100.0,
            policy="hold",
            supervised_probability=False,
        )
    )

    reset = result["trace"][0]
    assert reset["observations"]["scout"]["supervised_probability"] == 0.0
    assert reset["observations"]["trader"]["supervised_probability_available"] == 0.0
    assert reset["infos"]["portfolio"]["supervised_probability_enabled"] is False

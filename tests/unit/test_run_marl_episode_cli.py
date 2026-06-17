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
        )
    )

    assert result["steps"] == 2
    assert result["cash_available_eur"] == 90.0
    assert result["positions"] == [
        {
            "position_id": "pos-1",
            "item_id": "buff-to-steam",
            "item_name": "AK-47 | Slate_FT_0",
            "buy_platform": "BUFF",
            "buy_price_eur": 10.0,
            "purchased_at": "2026-01-01",
            "unlock_at": "2026-01-09",
        }
    ]
    first_step = result["trace"][1]
    assert first_step["actions"] == {"scout": 1, "trader": 1, "portfolio": 1}
    assert first_step["infos"]["trader"]["buy_platform"] == "BUFF"
    assert first_step["infos"]["trader"]["buy_price_type"] == "listing"
    assert first_step["infos"]["trader"]["sell_platform"] == "STEAM"


def test_run_marl_episode_hold_policy_does_not_buy() -> None:
    result = run(
        argparse.Namespace(
            dataset_dir=None,
            split="train",
            limit=5,
            cash=100.0,
            policy="hold",
        )
    )

    assert result["positions"] == []
    assert result["cash_available_eur"] == 100.0

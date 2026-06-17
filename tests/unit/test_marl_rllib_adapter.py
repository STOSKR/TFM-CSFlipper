from datetime import date
from decimal import Decimal

from packages.marl import (
    MarketEpisodeStep,
    MarketMARLEnvironment,
    market_env_creator,
    register_market_env,
)


def test_market_env_creator_builds_env_from_default_steps() -> None:
    creator = market_env_creator(_episode(), initial_cash_eur="50")

    env = creator({})
    observations, _infos = env.reset()

    assert isinstance(env, MarketMARLEnvironment)
    assert env.simulator.cash_available_eur == Decimal("50")
    assert observations["scout"]["buy_price_eur"] == 10.0


def test_register_market_env_exposes_rllib_style_creator() -> None:
    registered: dict[str, object] = {}

    register_market_env("csflipper-market", registered.__setitem__, _episode())

    creator = registered["csflipper-market"]
    assert callable(creator)
    env = creator({"initial_cash_eur": "75"})

    assert isinstance(env, MarketMARLEnvironment)
    assert env.simulator.cash_available_eur == Decimal("75")


def _episode() -> tuple[MarketEpisodeStep, ...]:
    return (
        MarketEpisodeStep(
            item_id="item-1",
            representation_name="AK-47 | Slate_FT_0",
            observed_day=date(2026, 1, 1),
            buy_price_eur=Decimal("10"),
            current_exit_net_eur=Decimal("12"),
            current_return=Decimal("0.2"),
            available_quantity=3,
            supervised_probability=Decimal("0.8"),
        ),
    )

from datetime import date
from decimal import Decimal

from packages.marl.market_env import (
    AGENT_IDS,
    AGENT_SPECS,
    MarketEpisodeStep,
    MarketMARLEnvironment,
)
from packages.marl.pettingzoo_env import PettingZooMarketEnv


def test_pettingzoo_market_env_runs_parallel_cycle() -> None:
    env = PettingZooMarketEnv(
        (
            MarketEpisodeStep(
                item_id="item-1",
                representation_name="AK-47 | Slate_FT_0",
                observed_day=date(2026, 1, 1),
                buy_price_eur=Decimal("10"),
                current_exit_net_eur=Decimal("12"),
                current_return=Decimal("0.2"),
                supervised_probability=Decimal("0.8"),
            ),
        ),
        initial_cash_eur=Decimal("100"),
    )

    observations, infos = env.reset()

    assert env.possible_agents == list(AGENT_IDS)
    assert env.agents == list(AGENT_IDS)
    assert observations["scout"].shape == (len(AGENT_SPECS["scout"].observation_fields),)
    assert env.observation_space("portfolio").shape == (
        len(AGENT_SPECS["portfolio"].observation_fields),
    )
    assert env.state_space().shape == (len(MarketMARLEnvironment.central_state_fields),)
    assert env.state().shape == env.state_space().shape
    assert env.action_space("trader").n == 3
    assert infos["scout"]["supervised_probability_available"] is True

    next_observations, rewards, terminations, truncations, step_infos = env.step(
        {"scout": 1, "trader": 1, "portfolio": 1}
    )

    assert next_observations == {}
    assert rewards["trader"] == 0.0
    assert terminations == {"scout": True, "trader": True, "portfolio": True}
    assert truncations == {"scout": False, "trader": False, "portfolio": False}
    assert step_infos["portfolio"]["executed_trade"] is True
    assert env.agents == []

from datetime import date
from decimal import Decimal

import pytest

from packages.marl import AGENT_IDS, AGENT_SPECS, MarketEpisodeStep, MarketMARLEnvironment
from packages.simulation import PortfolioRiskConfig


def test_market_marl_agent_specs_define_local_contracts() -> None:
    assert tuple(AGENT_SPECS) == AGENT_IDS
    assert AGENT_SPECS["scout"].executes_trades is False
    assert AGENT_SPECS["trader"].executes_trades is True
    assert AGENT_SPECS["portfolio"].executes_trades is False
    assert AGENT_SPECS["scout"].action_space == {0: "ignore", 1: "mark_opportunity"}
    assert AGENT_SPECS["trader"].observation_fields == (
        "buy_price_eur",
        "current_exit_net_eur",
        "current_return",
        "cash_available_ratio",
    )


def test_market_marl_env_reset_returns_agent_observations() -> None:
    env = MarketMARLEnvironment(_episode())

    observations, infos = env.reset()

    assert tuple(observations) == AGENT_IDS
    assert tuple(observations["scout"]) == AGENT_SPECS["scout"].observation_fields
    assert tuple(observations["trader"]) == AGENT_SPECS["trader"].observation_fields
    assert tuple(observations["portfolio"]) == AGENT_SPECS["portfolio"].observation_fields
    assert observations["scout"]["buy_price_eur"] == 10.0
    assert observations["scout"]["supervised_probability"] == 0.8
    assert observations["portfolio"]["candidate_position_ratio"] == 0.01
    assert infos["trader"]["representation_name"] == "AK-47 | Slate_FT_0"
    assert infos["trader"]["action_mask"] == (1, 1)


def test_market_marl_env_executes_buy_when_all_agents_accept() -> None:
    env = MarketMARLEnvironment(_episode(), initial_cash_eur=Decimal("100"))
    env.reset()

    observations, rewards, terminations, truncations, infos = env.step(
        {"scout": 1, "trader": 1, "portfolio": 1}
    )

    assert len(env.simulator.positions) == 1
    assert env.simulator.cash_available_eur == Decimal("90")
    assert rewards == {"scout": 0.2, "trader": 0.2, "portfolio": 0.2}
    assert observations["scout"]["buy_price_eur"] == 20.0
    assert terminations == {"scout": False, "trader": False, "portfolio": False}
    assert truncations == {"scout": False, "trader": False, "portfolio": False}
    assert infos["portfolio"]["executed_trade"] is True


@pytest.mark.parametrize(
    "actions",
    [
        {"scout": 1, "trader": 0, "portfolio": 1},
        {"scout": 0, "trader": 1, "portfolio": 1},
        {"scout": 1, "trader": 1, "portfolio": 0},
    ],
)
def test_market_marl_env_requires_all_agents_to_accept_before_buy(
    actions: dict[str, int],
) -> None:
    env = MarketMARLEnvironment(_episode(), initial_cash_eur=Decimal("100"))
    env.reset()

    _observations, rewards, _terminations, _truncations, infos = env.step(actions)

    assert env.simulator.positions == ()
    assert rewards == {"scout": 0.0, "trader": 0.0, "portfolio": 0.0}
    assert infos["trader"]["executed_trade"] is False


def test_market_marl_env_blocks_buy_when_portfolio_risk_rejects() -> None:
    env = MarketMARLEnvironment(
        _episode(),
        initial_cash_eur=Decimal("100"),
        risk_config=PortfolioRiskConfig(max_position_fraction=Decimal("0.05")),
    )
    env.reset()

    _observations, rewards, _terminations, _truncations, infos = env.step(
        {"scout": 1, "trader": 1, "portfolio": 1}
    )

    assert env.simulator.positions == ()
    assert rewards == {"scout": 0.0, "trader": 0.0, "portfolio": 0.0}
    assert infos["portfolio"]["executed_trade"] is False
    assert infos["portfolio"]["risk_violations"] == ("position_fraction",)


def test_market_marl_env_masks_buy_when_risk_rejects_candidate() -> None:
    env = MarketMARLEnvironment(
        _episode(),
        initial_cash_eur=Decimal("100"),
        risk_config=PortfolioRiskConfig(max_position_fraction=Decimal("0.05")),
    )

    _observations, infos = env.reset()

    assert env.action_masks() == {
        "scout": (1, 1),
        "trader": (1, 0),
        "portfolio": (1, 0),
    }
    assert infos["portfolio"]["action_mask"] == (1, 0)


def test_market_marl_env_rejects_invalid_actions() -> None:
    env = MarketMARLEnvironment(_episode())
    env.reset()

    with pytest.raises(ValueError, match="invalid action"):
        env.step({"scout": 2, "trader": 0, "portfolio": 0})

    with pytest.raises(ValueError, match="unknown agent"):
        env.step({"analyst": 1})


def test_market_marl_env_terminates_after_last_step() -> None:
    env = MarketMARLEnvironment(_episode()[:1])
    env.reset()

    observations, _rewards, terminations, truncations, _infos = env.step(
        {"scout": 0, "trader": 0, "portfolio": 0}
    )

    assert observations == {}
    assert terminations == {"scout": True, "trader": True, "portfolio": True}
    assert truncations == {"scout": False, "trader": False, "portfolio": False}
    assert env.agents == []


def test_market_episode_step_can_be_built_from_mapping() -> None:
    step = MarketEpisodeStep.from_mapping(
        {
            "item_id": "item-1",
            "representation_name": "AK-47 | Slate_FT_0",
            "observed_day": "2026-01-01",
            "buy_price_eur": "10",
            "current_exit_net_eur": "12",
            "current_return": "0.2",
            "available_quantity": "4",
            "supervised_probability": "0.8",
        }
    )

    assert step.observed_day == date(2026, 1, 1)
    assert step.buy_price_eur == Decimal("10")
    assert step.available_quantity == 4


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
        MarketEpisodeStep(
            item_id="item-2",
            representation_name="M4A1-S | Nitro_MW_0",
            observed_day=date(2026, 1, 2),
            buy_price_eur=Decimal("20"),
            current_exit_net_eur=Decimal("19"),
            current_return=Decimal("-0.05"),
            available_quantity=2,
            supervised_probability=Decimal("0.3"),
        ),
    )

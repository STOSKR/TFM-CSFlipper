from datetime import date
from decimal import Decimal

import pytest

from packages.marl import (
    AGENT_IDS,
    AGENT_SPECS,
    CENTRAL_STATE_FIELDS,
    MarketEpisodeStep,
    MarketMARLEnvironment,
)
from packages.simulation import BUFF, PortfolioRiskConfig


def test_market_marl_agent_specs_define_local_contracts() -> None:
    assert tuple(AGENT_SPECS) == AGENT_IDS
    assert AGENT_SPECS["scout"].executes_trades is False
    assert AGENT_SPECS["trader"].executes_trades is True
    assert AGENT_SPECS["portfolio"].executes_trades is False
    assert AGENT_SPECS["scout"].action_space == {0: "ignore", 1: "mark_opportunity"}
    assert AGENT_SPECS["trader"].observation_fields == (
        "buy_platform_is_steam",
        "buy_platform_is_buff",
        "buy_price_is_listing",
        "buy_price_is_buy_order",
        "sell_platform_is_steam",
        "sell_platform_is_buff",
        "sell_price_is_listing",
        "sell_price_is_buy_order",
        "buy_price_eur",
        "current_exit_net_eur",
        "current_return",
        "current_cash_value_eur",
        "current_cash_return",
        "supervised_probability",
        "supervised_probability_available",
        "cash_destination_is_reinvest",
        "cash_destination_is_cashout",
        "cash_available_ratio",
        "matching_sellable_positions",
        "matching_locked_positions",
    )


def test_market_marl_env_reset_returns_agent_observations() -> None:
    env = MarketMARLEnvironment(_episode())

    observations, infos = env.reset()

    assert tuple(observations) == AGENT_IDS
    assert tuple(observations["scout"]) == AGENT_SPECS["scout"].observation_fields
    assert tuple(observations["trader"]) == AGENT_SPECS["trader"].observation_fields
    assert tuple(observations["portfolio"]) == AGENT_SPECS["portfolio"].observation_fields
    assert observations["scout"]["buy_platform_is_steam"] == 1.0
    assert observations["scout"]["buy_platform_is_buff"] == 0.0
    assert observations["scout"]["buy_price_is_listing"] == 1.0
    assert observations["scout"]["buy_price_is_buy_order"] == 0.0
    assert observations["scout"]["sell_platform_is_steam"] == 1.0
    assert observations["scout"]["sell_price_is_listing"] == 1.0
    assert observations["scout"]["buy_price_eur"] == 10.0
    assert observations["scout"]["current_cash_return"] == 0.2
    assert observations["scout"]["supervised_probability"] == 0.8
    assert observations["scout"]["supervised_probability_available"] == 1.0
    assert observations["trader"]["current_cash_value_eur"] == 12.0
    assert observations["trader"]["supervised_probability"] == 0.8
    assert observations["trader"]["supervised_probability_available"] == 1.0
    assert observations["trader"]["cash_destination_is_reinvest"] == 1.0
    assert observations["trader"]["cash_destination_is_cashout"] == 0.0
    assert observations["portfolio"]["candidate_position_ratio"] == 0.01
    assert observations["portfolio"]["supervised_probability"] == 0.8
    assert observations["portfolio"]["supervised_probability_available"] == 1.0
    assert infos["trader"]["representation_name"] == "AK-47 | Slate_FT_0"
    assert infos["trader"]["route_label"] == "STEAM listing -> STEAM listing"
    assert infos["trader"]["route_selection"] == "candidate"
    assert infos["trader"]["cashflow"] == {
        "buy_value_eur": 10.0,
        "exit_balance_platform": "STEAM",
        "exit_balance_value_eur": 12.0,
        "effective_cash_value_eur": 12.0,
        "effective_cash_return": 0.2,
        "cash_destination": "reinvest",
    }
    assert infos["trader"]["supervised_probability_enabled"] is True
    assert infos["trader"]["supervised_probability_available"] is True
    assert infos["trader"]["central_state_fields"] == CENTRAL_STATE_FIELDS
    assert infos["trader"]["central_state"]["current_return"] == 0.2
    assert env.central_state()["cash_available_ratio"] == 1.0
    assert env.central_state()["candidate_position_ratio"] == 0.01
    assert infos["trader"]["action_mask"] == (1, 1, 0)


def test_market_marl_env_executes_buy_when_all_agents_accept() -> None:
    env = MarketMARLEnvironment(_episode(), initial_cash_eur=Decimal("100"))
    env.reset()

    observations, rewards, terminations, truncations, infos = env.step(
        {"scout": 1, "trader": 1, "portfolio": 1}
    )

    assert len(env.simulator.positions) == 1
    assert env.simulator.positions[0].buy_platform == "STEAM"
    assert env.simulator.cash_available_eur == Decimal("90")
    assert rewards == {"scout": 0.0, "trader": 0.0, "portfolio": 0.0}
    assert observations["scout"]["buy_price_eur"] == 20.0
    assert env.central_state()["current_return"] == -0.05
    assert terminations == {"scout": False, "trader": False, "portfolio": False}
    assert truncations == {"scout": False, "trader": False, "portfolio": False}
    assert infos["portfolio"]["executed_trade"] is True
    assert infos["portfolio"]["reward_breakdown"]["total"] == 0.0


def test_market_marl_env_step_info_describes_processed_item() -> None:
    env = MarketMARLEnvironment(_episode(), initial_cash_eur=Decimal("100"))
    env.reset()

    observations, _rewards, _terminations, _truncations, infos = env.step(
        {"scout": 1, "trader": 1, "portfolio": 1}
    )

    assert observations["scout"]["buy_price_eur"] == 20.0
    assert infos["trader"]["item_id"] == "item-1"
    assert infos["trader"]["observed_day"] == "2026-01-01"
    assert infos["trader"]["central_state"]["current_return"] == 0.2
    assert infos["trader"]["reward"] == 0.0
    assert infos["trader"]["individual_reward_breakdown"] == {
        "total": 0.0,
        "shared_component": 0.0,
        "individual_signal": 0.0,
        "individual_component": 0.0,
    }


def test_market_marl_central_state_is_separate_from_local_observations() -> None:
    env = MarketMARLEnvironment(_episode())

    observations, _infos = env.reset()
    central_state = env.central_state()

    assert tuple(central_state) == CENTRAL_STATE_FIELDS
    assert len(central_state) > len(observations["portfolio"])
    assert "current_cash_value_eur" in central_state
    assert "current_cash_value_eur" not in observations["portfolio"]
    assert "blocked_capital_ratio" in central_state
    assert "blocked_capital_ratio" not in observations["scout"]


def test_market_marl_env_can_execute_buy_from_buff_candidate() -> None:
    env = MarketMARLEnvironment(
        (
            MarketEpisodeStep(
                item_id="item-1",
                representation_name="AK-47 | Slate_FT_0",
                observed_day=date(2026, 1, 1),
                buy_platform=BUFF,
                buy_price_type="buy_order",
                sell_platform="STEAM",
                sell_price_type="buy_order",
                buy_price_eur=Decimal("10"),
                current_exit_net_eur=Decimal("12"),
                current_return=Decimal("0.2"),
            ),
        ),
        initial_cash_eur=Decimal("100"),
    )
    observations, _infos = env.reset()

    _next_observations, _rewards, _terminations, _truncations, infos = env.step(
        {"scout": 1, "trader": 1, "portfolio": 1}
    )

    assert observations["trader"]["buy_platform_is_steam"] == 0.0
    assert observations["trader"]["buy_platform_is_buff"] == 1.0
    assert observations["trader"]["buy_price_is_listing"] == 0.0
    assert observations["trader"]["buy_price_is_buy_order"] == 1.0
    assert observations["trader"]["sell_platform_is_steam"] == 1.0
    assert observations["trader"]["sell_price_is_buy_order"] == 1.0
    assert env.simulator.positions[0].buy_platform == "BUFF"
    assert env.simulator.positions[0].metadata["route_label"] == "BUFF buy_order -> STEAM buy_order"
    assert infos["trader"]["buy_platform"] == "BUFF"
    assert infos["trader"]["buy_price_type"] == "buy_order"
    assert infos["trader"]["sell_platform"] == "STEAM"
    assert infos["trader"]["sell_price_type"] == "buy_order"


@pytest.mark.parametrize(
    ("actions", "expected_rewards"),
    [
        (
            {"scout": 1, "trader": 0, "portfolio": 1},
            {"scout": 0.0, "trader": 0.0, "portfolio": 0.0},
        ),
        (
            {"scout": 0, "trader": 1, "portfolio": 1},
            {"scout": 0.0, "trader": 0.0, "portfolio": 0.0},
        ),
        (
            {"scout": 1, "trader": 1, "portfolio": 0},
            {"scout": 0.0, "trader": 0.0, "portfolio": 0.0},
        ),
    ],
)
def test_market_marl_env_requires_all_agents_to_accept_before_buy(
    actions: dict[str, int],
    expected_rewards: dict[str, float],
) -> None:
    env = MarketMARLEnvironment(_episode(), initial_cash_eur=Decimal("100"))
    env.reset()

    _observations, rewards, _terminations, _truncations, infos = env.step(actions)

    assert env.simulator.positions == ()
    assert rewards == expected_rewards
    assert infos["trader"]["executed_trade"] is False
    assert infos["trader"]["reward_breakdown"]["total"] == 0.0


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
    assert rewards == {"scout": -0.112, "trader": -0.172, "portfolio": -0.172}
    assert infos["portfolio"]["executed_trade"] is False
    assert infos["portfolio"]["risk_violations"] == ("position_fraction",)
    assert infos["portfolio"]["reward_breakdown"]["invalid_purchase"] == -0.16


def test_market_marl_env_masks_buy_when_risk_rejects_candidate() -> None:
    env = MarketMARLEnvironment(
        _episode(),
        initial_cash_eur=Decimal("100"),
        risk_config=PortfolioRiskConfig(max_position_fraction=Decimal("0.05")),
    )

    _observations, infos = env.reset()

    assert env.action_masks() == {
        "scout": (1, 1),
        "trader": (1, 0, 0),
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
            "buy_platform": "buff",
            "buy_mode": "Buy via STEAM Buy Order",
            "sell_platform": "steam",
            "sell_mode": "Sell to STEAM Highest Buy Order",
            "current_exit_net_eur": "12",
            "current_return": "0.2",
            "current_cash_value_eur": "11",
            "current_cash_return": "0.1",
            "cash_destination": "cashout",
            "available_quantity": "4",
            "supervised_probability": "0.8",
            "supervised_model_version": "calibrated-v1",
            "volatility": "0.3",
        }
    )

    assert step.observed_day == date(2026, 1, 1)
    assert step.buy_price_eur == Decimal("10")
    assert step.buy_platform == "BUFF"
    assert step.buy_price_type == "buy_order"
    assert step.sell_platform == "STEAM"
    assert step.sell_price_type == "buy_order"
    assert step.current_cash_value_eur == Decimal("11")
    assert step.current_cash_return == Decimal("0.1")
    assert step.cash_destination == "cashout"
    assert step.route_label == "BUFF buy_order -> STEAM buy_order"
    assert step.supervised_model_version == "calibrated-v1"
    assert step.available_quantity == 4
    assert step.volatility == Decimal("0.3")


def test_market_episode_step_ignores_legacy_cash_return_without_cash_value() -> None:
    step = MarketEpisodeStep.from_mapping(
        {
            "item_id": "item-1",
            "representation_name": "AK-47 | Slate_FT_0",
            "observed_day": "2026-01-01",
            "buy_price_eur": "10",
            "current_exit_net_eur": "12",
            "current_return": "0.2",
            "current_cash_return": "-0.3",
        }
    )

    assert step.current_cash_value_eur is None
    assert step.current_cash_return is None


def test_market_marl_env_values_cashout_destination_separately_from_platform_balance() -> None:
    env = MarketMARLEnvironment(
        (
            MarketEpisodeStep(
                item_id="item-1",
                representation_name="AK-47 | Slate_FT_0",
                observed_day=date(2026, 1, 1),
                buy_price_eur=Decimal("10"),
                current_exit_net_eur=Decimal("12"),
                current_return=Decimal("0.2"),
                cash_destination="cashout",
            ),
        ),
        initial_cash_eur=Decimal("100"),
    )

    observations, infos = env.reset()

    assert observations["trader"]["current_cash_value_eur"] == 9.6
    assert observations["trader"]["current_cash_return"] == -0.04
    assert observations["trader"]["cash_destination_is_reinvest"] == 0.0
    assert observations["trader"]["cash_destination_is_cashout"] == 1.0
    assert infos["scout"]["cashflow"]["exit_balance_value_eur"] == 12.0
    assert infos["scout"]["cashflow"]["effective_cash_value_eur"] == 9.6


def test_market_marl_env_can_disable_supervised_probability_feature() -> None:
    env = MarketMARLEnvironment(
        _episode(),
        include_supervised_probability=False,
    )

    observations, infos = env.reset()

    for agent_id in AGENT_IDS:
        assert observations[agent_id]["supervised_probability"] == 0.0
        assert observations[agent_id]["supervised_probability_available"] == 0.0
        assert infos[agent_id]["supervised_probability_enabled"] is False
        assert infos[agent_id]["supervised_probability_available"] is False


def test_market_marl_env_blocks_sale_until_trade_hold_ends() -> None:
    env = MarketMARLEnvironment(_sale_episode(), initial_cash_eur=Decimal("100"))
    _observations, _infos = env.reset()

    observations, _rewards, _terminations, _truncations, _infos = env.step(
        {"scout": 1, "trader": 1, "portfolio": 1}
    )

    assert observations["trader"]["matching_sellable_positions"] == 0.0
    assert env.simulator.positions[0].unlock_at == date(2026, 1, 9)
    assert env.action_masks()["trader"] == (1, 1, 0)


def test_market_marl_env_sells_matching_position_after_trade_hold() -> None:
    env = MarketMARLEnvironment(_sale_episode(), initial_cash_eur=Decimal("100"))
    _observations, _infos = env.reset()
    observations, _rewards, _terminations, _truncations, _infos = env.step(
        {"scout": 1, "trader": 1, "portfolio": 1}
    )

    observations, _rewards, _terminations, _truncations, _infos = env.step(
        {"scout": 0, "trader": 0, "portfolio": 0}
    )

    assert observations["trader"]["matching_sellable_positions"] == 1.0
    assert env.action_masks()["trader"] == (1, 1, 1)

    _observations, rewards, terminations, _truncations, infos = env.step(
        {"scout": 0, "trader": 2, "portfolio": 1}
    )

    position = env.simulator.positions[0]
    assert position.sold_at == date(2026, 1, 9)
    assert position.net_sale_value_eur == Decimal("12.18")
    assert position.realized_profit_eur == Decimal("2.18")
    assert env.simulator.cash_available_eur == Decimal("102.18")
    assert infos["trader"]["executed_buy"] is False
    assert infos["trader"]["executed_sale"] is True
    assert infos["trader"]["sold_position_id"] == "pos-1"
    assert rewards["trader"] == pytest.approx(0.09156)
    assert terminations["trader"] is True


def test_market_marl_env_penalizes_scout_after_an_affordable_missed_opportunity() -> None:
    env = MarketMARLEnvironment(_sale_episode(), initial_cash_eur=Decimal("100"))
    _observations, _infos = env.reset()

    env.step({"scout": 0, "trader": 0, "portfolio": 0})
    env.step({"scout": 0, "trader": 0, "portfolio": 0})
    _observations, rewards, _terminations, _truncations, infos = env.step(
        {"scout": 0, "trader": 0, "portfolio": 0}
    )

    assert infos["scout"]["reward_breakdown"]["total"] == 0.0
    assert rewards["scout"] == pytest.approx(-0.0654)
    assert rewards["trader"] == 0.0


def test_market_marl_env_keeps_supervised_observation_shape_when_prediction_is_missing() -> None:
    env = MarketMARLEnvironment(
        (
            MarketEpisodeStep(
                item_id="item-1",
                representation_name="AK-47 | Slate_FT_0",
                observed_day=date(2026, 1, 1),
                buy_price_eur=Decimal("10"),
                current_exit_net_eur=Decimal("12"),
                current_return=Decimal("0.2"),
                supervised_probability=None,
            ),
        ),
    )

    observations, infos = env.reset()

    for agent_id in AGENT_IDS:
        assert tuple(observations[agent_id]) == AGENT_SPECS[agent_id].observation_fields
        assert observations[agent_id]["supervised_probability"] == 0.0
        assert observations[agent_id]["supervised_probability_available"] == 0.0
        assert infos[agent_id]["supervised_probability_enabled"] is True
        assert infos[agent_id]["supervised_probability_available"] is False


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


def _sale_episode() -> tuple[MarketEpisodeStep, ...]:
    return (
        MarketEpisodeStep(
            item_id="item-1",
            representation_name="AK-47 | Slate_FT_0",
            observed_day=date(2026, 1, 1),
            buy_platform=BUFF,
            buy_price_eur=Decimal("10"),
            current_exit_net_eur=Decimal("12"),
            current_return=Decimal("0.2"),
            steam_sell_price_eur=Decimal("12"),
            available_quantity=3,
        ),
        MarketEpisodeStep(
            item_id="item-1",
            representation_name="AK-47 | Slate_FT_0",
            observed_day=date(2026, 1, 2),
            buy_platform=BUFF,
            buy_price_eur=Decimal("10"),
            current_exit_net_eur=Decimal("10.44"),
            current_return=Decimal("0.044"),
            current_exit_gross_price_eur=Decimal("12"),
            available_quantity=3,
        ),
        MarketEpisodeStep(
            item_id="item-1",
            representation_name="AK-47 | Slate_FT_0",
            observed_day=date(2026, 1, 9),
            buy_platform=BUFF,
            buy_price_eur=Decimal("11"),
            current_exit_net_eur=Decimal("12.18"),
            current_return=Decimal("0.1073"),
            current_exit_gross_price_eur=Decimal("14"),
            available_quantity=3,
        ),
    )

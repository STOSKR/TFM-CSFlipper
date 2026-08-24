from datetime import date
from decimal import Decimal

from packages.marl.rewards import (
    CooperativeRewardConfig,
    HybridRewardConfig,
    calculate_agent_reward_breakdowns,
    calculate_cooperative_reward,
    shared_reward_map,
)
from packages.simulation import PortfolioMetrics


def test_cooperative_reward_includes_realized_profit() -> None:
    breakdown = calculate_cooperative_reward(
        before_metrics=_metrics(realized_profit_eur=Decimal("0")),
        after_metrics=_metrics(realized_profit_eur=Decimal("10")),
        executed_trade=False,
        opportunity_available=False,
    )

    assert breakdown.realized_profit == Decimal("0.1")
    assert breakdown.total == Decimal("0.1")


def test_cooperative_reward_includes_realized_loss() -> None:
    breakdown = calculate_cooperative_reward(
        before_metrics=_metrics(realized_profit_eur=Decimal("0")),
        after_metrics=_metrics(realized_profit_eur=Decimal("-5")),
        executed_trade=False,
        opportunity_available=False,
    )

    assert breakdown.realized_profit == Decimal("-0.05")
    assert breakdown.total == Decimal("-0.05")


def test_cooperative_reward_penalizes_inactivity_when_opportunity_is_actionable() -> None:
    breakdown = calculate_cooperative_reward(
        before_metrics=_metrics(),
        after_metrics=_metrics(),
        executed_trade=False,
        opportunity_available=True,
        config=CooperativeRewardConfig(inactivity_penalty=Decimal("0.02")),
    )

    assert breakdown.inactivity == Decimal("-0.02")
    assert breakdown.total == Decimal("-0.02")


def test_cooperative_reward_penalizes_risk_violations_even_with_gross_return() -> None:
    breakdown = calculate_cooperative_reward(
        before_metrics=_metrics(),
        after_metrics=_metrics(),
        executed_trade=True,
        opportunity_available=True,
        opportunity_return=Decimal("0.03"),
        risk_violations=("position_fraction", "cash_floor"),
        config=CooperativeRewardConfig(risk_violation_penalty=Decimal("0.05")),
    )

    assert breakdown.executed_return == Decimal("0.03")
    assert breakdown.risk_violation == Decimal("-0.10")
    assert breakdown.total == Decimal("-0.07")


def test_cooperative_reward_penalizes_drawdown_blocked_capital_and_volatility() -> None:
    breakdown = calculate_cooperative_reward(
        before_metrics=_metrics(),
        after_metrics=_metrics(
            capital_blocked_eur=Decimal("20"),
            equity_eur=Decimal("100"),
            drawdown_ratio=Decimal("0.10"),
        ),
        executed_trade=False,
        opportunity_available=False,
        candidate_volatility=Decimal("0.30"),
    )

    assert breakdown.drawdown == Decimal("-0.050")
    assert breakdown.blocked_capital == Decimal("-0.010")
    assert breakdown.volatility == Decimal("-0.030")
    assert breakdown.total == Decimal("-0.090")


def test_shared_reward_map_returns_same_reward_for_every_agent() -> None:
    breakdown = calculate_cooperative_reward(
        before_metrics=_metrics(),
        after_metrics=_metrics(),
        executed_trade=True,
        opportunity_available=True,
        opportunity_return=Decimal("0.2"),
    )

    assert shared_reward_map(("scout", "trader", "portfolio"), breakdown) == {
        "scout": 0.2,
        "trader": 0.2,
        "portfolio": 0.2,
    }


def test_hybrid_reward_rewards_each_role_for_its_own_action() -> None:
    shared_breakdown = calculate_cooperative_reward(
        before_metrics=_metrics(),
        after_metrics=_metrics(),
        executed_trade=False,
        opportunity_available=True,
    )

    rewards = calculate_agent_reward_breakdowns(
        agents=("scout", "trader", "portfolio"),
        shared_breakdown=shared_breakdown,
        actions={"scout": 1, "trader": 0, "portfolio": 1},
        executed_buy=False,
        executed_sale=False,
        opportunity_available=True,
        candidate_return=Decimal("0.2"),
        cooperative_config=CooperativeRewardConfig(inactivity_penalty=Decimal("0.01")),
        hybrid_config=HybridRewardConfig(shared_weight=Decimal("0.70")),
    )

    assert rewards["scout"].individual_signal == Decimal("0.2")
    assert rewards["trader"].individual_signal == Decimal("-0.01")
    assert rewards["portfolio"].individual_signal == Decimal("0.2")
    assert rewards["scout"].total == Decimal("0.053")
    assert rewards["trader"].total == Decimal("-0.010")


def test_hybrid_reward_penalizes_portfolio_approval_of_risk_violation() -> None:
    shared_breakdown = calculate_cooperative_reward(
        before_metrics=_metrics(),
        after_metrics=_metrics(),
        executed_trade=False,
        opportunity_available=False,
        risk_violations=("position_fraction",),
    )

    rewards = calculate_agent_reward_breakdowns(
        agents=("scout", "trader", "portfolio"),
        shared_breakdown=shared_breakdown,
        actions={"scout": 1, "trader": 1, "portfolio": 1},
        executed_buy=False,
        executed_sale=False,
        opportunity_available=False,
        risk_violations=("position_fraction",),
    )

    assert rewards["portfolio"].individual_signal == Decimal("-0.05")
    assert rewards["portfolio"].total == Decimal("-0.050")
    assert rewards["scout"].total == Decimal("-0.035")


def _metrics(
    *,
    realized_profit_eur: Decimal = Decimal("0"),
    capital_blocked_eur: Decimal = Decimal("0"),
    equity_eur: Decimal = Decimal("100"),
    drawdown_ratio: Decimal = Decimal("0"),
) -> PortfolioMetrics:
    return PortfolioMetrics(
        as_of=date(2026, 1, 1),
        initial_cash_eur=Decimal("100"),
        cash_available_eur=Decimal("100") - capital_blocked_eur,
        capital_blocked_eur=capital_blocked_eur,
        open_invested_eur=capital_blocked_eur,
        realized_profit_eur=realized_profit_eur,
        unrealized_profit_eur=Decimal("0"),
        equity_eur=equity_eur,
        peak_equity_eur=Decimal("100"),
        drawdown_eur=drawdown_ratio * Decimal("100"),
        drawdown_ratio=drawdown_ratio,
        locked_positions=0,
        open_positions=0,
        closed_positions=0,
    )

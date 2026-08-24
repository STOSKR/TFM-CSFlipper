"""Shared and individual reward shaping for the MARL market environment."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal

from packages.simulation import PortfolioMetrics


@dataclass(frozen=True, slots=True)
class CooperativeRewardConfig:
    realized_profit_scale_eur: Decimal = Decimal("100")
    executed_return_weight: Decimal = Decimal("1")
    inactivity_penalty: Decimal = Decimal("0.01")
    risk_violation_penalty: Decimal = Decimal("0.05")
    drawdown_penalty_weight: Decimal = Decimal("0.50")
    blocked_capital_penalty_weight: Decimal = Decimal("0.05")
    volatility_penalty_weight: Decimal = Decimal("0.10")

    def __post_init__(self) -> None:
        if self.realized_profit_scale_eur <= 0:
            raise ValueError("realized_profit_scale_eur must be greater than zero")
        for field_name in (
            "executed_return_weight",
            "inactivity_penalty",
            "risk_violation_penalty",
            "drawdown_penalty_weight",
            "blocked_capital_penalty_weight",
            "volatility_penalty_weight",
        ):
            if getattr(self, field_name) < 0:
                raise ValueError(f"{field_name} must be non-negative")


@dataclass(frozen=True, slots=True)
class HybridRewardConfig:
    """Combines the common portfolio reward with a role-specific signal."""

    shared_weight: Decimal = Decimal("0.70")

    def __post_init__(self) -> None:
        if not Decimal("0") <= self.shared_weight <= Decimal("1"):
            raise ValueError("shared_weight must be between zero and one")


@dataclass(frozen=True, slots=True)
class CooperativeRewardBreakdown:
    realized_profit: Decimal
    executed_return: Decimal
    inactivity: Decimal
    risk_violation: Decimal
    drawdown: Decimal
    blocked_capital: Decimal
    volatility: Decimal

    @property
    def total(self) -> Decimal:
        return (
            self.realized_profit
            + self.executed_return
            + self.inactivity
            + self.risk_violation
            + self.drawdown
            + self.blocked_capital
            + self.volatility
        )

    def as_float_dict(self) -> dict[str, float]:
        return {
            "total": float(self.total),
            "realized_profit": float(self.realized_profit),
            "executed_return": float(self.executed_return),
            "inactivity": float(self.inactivity),
            "risk_violation": float(self.risk_violation),
            "drawdown": float(self.drawdown),
            "blocked_capital": float(self.blocked_capital),
            "volatility": float(self.volatility),
        }


@dataclass(frozen=True, slots=True)
class AgentRewardBreakdown:
    """Reward received by one agent after combining both reward components."""

    shared_component: Decimal
    individual_signal: Decimal
    individual_component: Decimal

    @property
    def total(self) -> Decimal:
        return self.shared_component + self.individual_component

    def as_float_dict(self) -> dict[str, float]:
        return {
            "total": float(self.total),
            "shared_component": float(self.shared_component),
            "individual_signal": float(self.individual_signal),
            "individual_component": float(self.individual_component),
        }


def calculate_cooperative_reward(
    *,
    before_metrics: PortfolioMetrics,
    after_metrics: PortfolioMetrics,
    executed_trade: bool,
    opportunity_available: bool,
    risk_violations: tuple[str, ...] = (),
    opportunity_return: Decimal | None = None,
    candidate_volatility: Decimal | None = None,
    config: CooperativeRewardConfig | None = None,
) -> CooperativeRewardBreakdown:
    reward_config = config or CooperativeRewardConfig()
    realized_delta = after_metrics.realized_profit_eur - before_metrics.realized_profit_eur
    realized_profit = realized_delta / reward_config.realized_profit_scale_eur
    executed_return = (
        (opportunity_return or Decimal("0")) * reward_config.executed_return_weight
        if executed_trade
        else Decimal("0")
    )
    inactivity = (
        -reward_config.inactivity_penalty
        if opportunity_available and not executed_trade
        else Decimal("0")
    )
    risk_violation = -reward_config.risk_violation_penalty * Decimal(len(risk_violations))
    drawdown = -after_metrics.drawdown_ratio * reward_config.drawdown_penalty_weight
    blocked_capital = (
        -_ratio(after_metrics.capital_blocked_eur, _portfolio_denominator(after_metrics))
        * reward_config.blocked_capital_penalty_weight
    )
    volatility = (
        -(candidate_volatility or Decimal("0")) * reward_config.volatility_penalty_weight
    )
    return CooperativeRewardBreakdown(
        realized_profit=realized_profit,
        executed_return=executed_return,
        inactivity=inactivity,
        risk_violation=risk_violation,
        drawdown=drawdown,
        blocked_capital=blocked_capital,
        volatility=volatility,
    )


def shared_reward_map(
    agents: tuple[str, ...],
    breakdown: CooperativeRewardBreakdown,
) -> dict[str, float]:
    reward = float(breakdown.total)
    return {agent_id: reward for agent_id in agents}


def calculate_agent_reward_breakdowns(
    *,
    agents: tuple[str, ...],
    shared_breakdown: CooperativeRewardBreakdown,
    actions: Mapping[str, int],
    executed_buy: bool,
    executed_sale: bool,
    opportunity_available: bool,
    risk_violations: tuple[str, ...] = (),
    candidate_return: Decimal | None = None,
    executed_return: Decimal | None = None,
    cooperative_config: CooperativeRewardConfig | None = None,
    hybrid_config: HybridRewardConfig | None = None,
) -> dict[str, AgentRewardBreakdown]:
    """Return one hybrid reward for Scout, Trader and Portfolio.

    The individual signal measures whether each role fulfilled its own task. The
    shared component remains present for every agent, so no role can improve its
    own reward while ignoring the simulated portfolio.
    """

    reward_config = cooperative_config or CooperativeRewardConfig()
    mix_config = hybrid_config or HybridRewardConfig()
    candidate_signal = candidate_return or Decimal("0")
    execution_signal = executed_return if executed_return is not None else candidate_signal
    scout_action = int(actions.get("scout", 0))
    trader_action = int(actions.get("trader", 0))
    portfolio_action = int(actions.get("portfolio", 0))

    signals = {
        "scout": _scout_signal(
            action=scout_action,
            opportunity_available=opportunity_available,
            executed_sale=executed_sale,
            candidate_return=candidate_signal,
            inactivity_penalty=reward_config.inactivity_penalty,
        ),
        "trader": _trader_signal(
            action=trader_action,
            executed_buy=executed_buy,
            executed_sale=executed_sale,
            opportunity_available=opportunity_available,
            candidate_return=candidate_signal,
            execution_return=execution_signal,
            inactivity_penalty=reward_config.inactivity_penalty,
        ),
        "portfolio": _portfolio_signal(
            action=portfolio_action,
            executed_buy=executed_buy,
            executed_sale=executed_sale,
            opportunity_available=opportunity_available,
            risk_violations=risk_violations,
            candidate_return=candidate_signal,
            execution_return=execution_signal,
            inactivity_penalty=reward_config.inactivity_penalty,
            risk_violation_penalty=reward_config.risk_violation_penalty,
        ),
    }
    shared_component = shared_breakdown.total * mix_config.shared_weight
    individual_weight = Decimal("1") - mix_config.shared_weight
    return {
        agent_id: AgentRewardBreakdown(
            shared_component=shared_component,
            individual_signal=signals.get(agent_id, Decimal("0")),
            individual_component=signals.get(agent_id, Decimal("0")) * individual_weight,
        )
        for agent_id in agents
    }


def agent_reward_map(
    breakdowns: Mapping[str, AgentRewardBreakdown],
) -> dict[str, float]:
    return {agent_id: float(breakdown.total) for agent_id, breakdown in breakdowns.items()}


def reward_info(
    breakdown: CooperativeRewardBreakdown,
) -> Mapping[str, float]:
    return breakdown.as_float_dict()


def agent_reward_info(
    breakdown: AgentRewardBreakdown,
) -> Mapping[str, float]:
    return breakdown.as_float_dict()


def _scout_signal(
    *,
    action: int,
    opportunity_available: bool,
    executed_sale: bool,
    candidate_return: Decimal,
    inactivity_penalty: Decimal,
) -> Decimal:
    if executed_sale or not opportunity_available:
        return Decimal("0")
    return candidate_return if action == 1 else -inactivity_penalty


def _trader_signal(
    *,
    action: int,
    executed_buy: bool,
    executed_sale: bool,
    opportunity_available: bool,
    candidate_return: Decimal,
    execution_return: Decimal,
    inactivity_penalty: Decimal,
) -> Decimal:
    if executed_buy or executed_sale:
        return execution_return
    if opportunity_available:
        return candidate_return if action == 1 else -inactivity_penalty
    return Decimal("0")


def _portfolio_signal(
    *,
    action: int,
    executed_buy: bool,
    executed_sale: bool,
    opportunity_available: bool,
    risk_violations: tuple[str, ...],
    candidate_return: Decimal,
    execution_return: Decimal,
    inactivity_penalty: Decimal,
    risk_violation_penalty: Decimal,
) -> Decimal:
    if risk_violations and action == 1:
        return -risk_violation_penalty * Decimal(len(risk_violations))
    if executed_buy or executed_sale:
        return execution_return if action == 1 else Decimal("0")
    if opportunity_available:
        return candidate_return if action == 1 else -inactivity_penalty
    return Decimal("0")


def _portfolio_denominator(metrics: PortfolioMetrics) -> Decimal:
    if metrics.equity_eur > 0:
        return metrics.equity_eur
    if metrics.initial_cash_eur > 0:
        return metrics.initial_cash_eur
    return Decimal("1")


def _ratio(numerator: Decimal, denominator: Decimal) -> Decimal:
    if denominator <= 0:
        return Decimal("0")
    return numerator / denominator

"""Deterministic portfolio risk limits for the future MARL Portfolio agent."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from types import MappingProxyType

from packages.simulation.portfolio import MarketMark, PortfolioMetrics, PortfolioSimulator


@dataclass(frozen=True, slots=True)
class PortfolioRiskConfig:
    max_position_fraction: Decimal = Decimal("0.20")
    max_item_fraction: Decimal = Decimal("0.30")
    max_platform_fraction: Decimal = Decimal("0.70")
    max_blocked_fraction: Decimal = Decimal("0.60")
    min_cash_fraction: Decimal = Decimal("0.10")
    min_liquidity_quantity: int = 1
    max_volatility: Decimal | None = None
    warning_usage_ratio: Decimal = Decimal("0.80")

    def __post_init__(self) -> None:
        _require_unit_interval(self.max_position_fraction, "max_position_fraction")
        _require_unit_interval(self.max_item_fraction, "max_item_fraction")
        _require_unit_interval(self.max_platform_fraction, "max_platform_fraction")
        _require_unit_interval(self.max_blocked_fraction, "max_blocked_fraction")
        _require_unit_interval(self.min_cash_fraction, "min_cash_fraction")
        _require_unit_interval(self.warning_usage_ratio, "warning_usage_ratio")
        if self.min_liquidity_quantity < 0:
            raise ValueError("min_liquidity_quantity must be non-negative")
        if self.max_volatility is not None and self.max_volatility < 0:
            raise ValueError("max_volatility must be non-negative")


@dataclass(frozen=True, slots=True)
class RiskCandidate:
    item_id: str
    buy_platform: str
    buy_value_eur: Decimal
    available_quantity: int | None = None
    volatility: Decimal | None = None

    def __post_init__(self) -> None:
        if not self.item_id.strip():
            raise ValueError("item_id cannot be empty")
        if not self.buy_platform.strip():
            raise ValueError("buy_platform cannot be empty")
        if self.buy_value_eur <= 0:
            raise ValueError("buy_value_eur must be greater than zero")
        if self.available_quantity is not None and self.available_quantity < 0:
            raise ValueError("available_quantity must be non-negative")
        if self.volatility is not None and self.volatility < 0:
            raise ValueError("volatility must be non-negative")


@dataclass(frozen=True, slots=True)
class RiskLimitMetric:
    name: str
    value: Decimal
    limit: Decimal
    usage_ratio: Decimal
    breached: bool
    warning: bool

    @property
    def remaining(self) -> Decimal:
        return self.limit - self.value


@dataclass(frozen=True, slots=True)
class PortfolioRiskSnapshot:
    metrics: PortfolioMetrics
    limits: MappingProxyType[str, RiskLimitMetric]
    observation: MappingProxyType[str, Decimal]
    violations: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def candidate_allowed(self) -> bool:
        return not self.violations


def default_portfolio_risk_config() -> PortfolioRiskConfig:
    return PortfolioRiskConfig()


def evaluate_portfolio_risk(
    simulator: PortfolioSimulator,
    *,
    as_of: date,
    config: PortfolioRiskConfig | None = None,
    candidate: RiskCandidate | None = None,
    marks: Mapping[str, MarketMark] | None = None,
) -> PortfolioRiskSnapshot:
    risk_config = config or default_portfolio_risk_config()
    metrics = simulator.metrics(as_of=as_of, marks=marks)
    denominator = _positive_denominator(metrics)
    candidate_value = candidate.buy_value_eur if candidate else Decimal("0")
    item_exposure = _item_exposure(simulator, candidate)
    platform_exposure = _platform_exposure(simulator, candidate)
    blocked_capital = metrics.capital_blocked_eur + candidate_value
    cash_after_candidate = metrics.cash_available_eur - candidate_value

    limits: dict[str, RiskLimitMetric] = {
        "position_fraction": _max_limit(
            "position_fraction",
            candidate_value,
            denominator * risk_config.max_position_fraction,
            risk_config,
        ),
        "item_fraction": _max_limit(
            "item_fraction",
            item_exposure,
            denominator * risk_config.max_item_fraction,
            risk_config,
        ),
        "platform_fraction": _max_limit(
            "platform_fraction",
            platform_exposure,
            denominator * risk_config.max_platform_fraction,
            risk_config,
        ),
        "blocked_fraction": _max_limit(
            "blocked_fraction",
            blocked_capital,
            denominator * risk_config.max_blocked_fraction,
            risk_config,
        ),
        "cash_floor": _min_limit(
            "cash_floor",
            cash_after_candidate,
            denominator * risk_config.min_cash_fraction,
            risk_config,
        ),
    }
    if candidate is not None and candidate.available_quantity is not None:
        limits["liquidity"] = _min_limit(
            "liquidity",
            Decimal(candidate.available_quantity),
            Decimal(risk_config.min_liquidity_quantity),
            risk_config,
        )
    if (
        candidate is not None
        and candidate.volatility is not None
        and risk_config.max_volatility is not None
    ):
        limits["volatility"] = _max_limit(
            "volatility",
            candidate.volatility,
            risk_config.max_volatility,
            risk_config,
        )

    violations = tuple(name for name, metric in limits.items() if metric.breached)
    warnings = tuple(
        name for name, metric in limits.items() if metric.warning and not metric.breached
    )
    observation = {
        "cash_available_ratio": _ratio(metrics.cash_available_eur, denominator),
        "cash_after_candidate_ratio": _ratio(cash_after_candidate, denominator),
        "blocked_capital_ratio": _ratio(blocked_capital, denominator),
        "open_exposure_ratio": _ratio(metrics.open_invested_eur + candidate_value, denominator),
        "drawdown_ratio": metrics.drawdown_ratio,
        "item_exposure_ratio": _ratio(item_exposure, denominator),
        "platform_exposure_ratio": _ratio(platform_exposure, denominator),
        "candidate_position_ratio": _ratio(candidate_value, denominator),
        "violation_count": Decimal(len(violations)),
        "warning_count": Decimal(len(warnings)),
    }
    return PortfolioRiskSnapshot(
        metrics=metrics,
        limits=MappingProxyType(limits),
        observation=MappingProxyType(observation),
        violations=violations,
        warnings=warnings,
    )


def _item_exposure(
    simulator: PortfolioSimulator,
    candidate: RiskCandidate | None,
) -> Decimal:
    if candidate is None:
        exposures: dict[str, Decimal] = {}
        for position in simulator.positions:
            if not position.is_closed:
                exposures[position.item_id] = (
                    exposures.get(position.item_id, Decimal("0")) + position.invested_eur
                )
        return max(exposures.values(), default=Decimal("0"))
    return sum(
        (
            position.invested_eur
            for position in simulator.positions
            if not position.is_closed and position.item_id == candidate.item_id
        ),
        candidate.buy_value_eur,
    )


def _platform_exposure(
    simulator: PortfolioSimulator,
    candidate: RiskCandidate | None,
) -> Decimal:
    if candidate is None:
        exposures: dict[str, Decimal] = {}
        for position in simulator.positions:
            if not position.is_closed:
                exposures[position.buy_platform] = (
                    exposures.get(position.buy_platform, Decimal("0")) + position.invested_eur
                )
        return max(exposures.values(), default=Decimal("0"))
    platform = candidate.buy_platform.upper()
    return sum(
        (
            position.invested_eur
            for position in simulator.positions
            if not position.is_closed and position.buy_platform == platform
        ),
        candidate.buy_value_eur,
    )


def _max_limit(
    name: str,
    value: Decimal,
    limit: Decimal,
    config: PortfolioRiskConfig,
) -> RiskLimitMetric:
    usage = _ratio(value, limit)
    return RiskLimitMetric(
        name=name,
        value=value,
        limit=limit,
        usage_ratio=usage,
        breached=value > limit,
        warning=usage >= config.warning_usage_ratio,
    )


def _min_limit(
    name: str,
    value: Decimal,
    limit: Decimal,
    config: PortfolioRiskConfig,
) -> RiskLimitMetric:
    usage = _ratio(limit, value)
    return RiskLimitMetric(
        name=name,
        value=value,
        limit=limit,
        usage_ratio=usage,
        breached=value < limit,
        warning=usage >= config.warning_usage_ratio,
    )


def _positive_denominator(metrics: PortfolioMetrics) -> Decimal:
    if metrics.equity_eur > 0:
        return metrics.equity_eur
    if metrics.initial_cash_eur > 0:
        return metrics.initial_cash_eur
    return Decimal("1")


def _ratio(numerator: Decimal, denominator: Decimal) -> Decimal:
    if denominator <= 0:
        return Decimal("0")
    return numerator / denominator


def _require_unit_interval(value: Decimal, field_name: str) -> None:
    if value < 0 or value > 1:
        raise ValueError(f"{field_name} must be in [0, 1]")

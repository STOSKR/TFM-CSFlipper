"""Recompensas comunes e individuales del entorno MARL de mercado.

La recompensa común solo valora el resultado verificable de una operación
cerrada o el incumplimiento de una restricción. Las señales de cada rol no
sustituyen ese resultado: atribuyen una parte adicional de la señal a la
decisión que correspondía a Scout, Trader o Portfolio.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class CooperativeRewardConfig:
    """Pesos configurables de la recompensa definida en la Sección 4.4."""

    roi_weight: Decimal = Decimal("0.60")
    extra_hold_day_penalty: Decimal = Decimal("0.01")
    constraint_violation_penalty: Decimal = Decimal("0.80")

    def __post_init__(self) -> None:
        for field_name in (
            "roi_weight",
            "extra_hold_day_penalty",
            "constraint_violation_penalty",
        ):
            if getattr(self, field_name) < 0:
                raise ValueError(f"{field_name} must be non-negative")


@dataclass(frozen=True, slots=True)
class HybridRewardConfig:
    """Mezcla la recompensa común con la señal individual de cada rol."""

    shared_weight: Decimal = Decimal("0.70")

    def __post_init__(self) -> None:
        if not Decimal("0") <= self.shared_weight <= Decimal("1"):
            raise ValueError("shared_weight must be between zero and one")


@dataclass(frozen=True, slots=True)
class CooperativeRewardBreakdown:
    """Componentes de la recompensa común para una transición."""

    closed_operation_roi: Decimal
    extra_hold_days: Decimal
    invalid_purchase: Decimal

    @property
    def total(self) -> Decimal:
        return self.closed_operation_roi + self.extra_hold_days + self.invalid_purchase

    def as_float_dict(self) -> dict[str, float]:
        return {
            "total": float(self.total),
            "closed_operation_roi": float(self.closed_operation_roi),
            "extra_hold_days": float(self.extra_hold_days),
            "invalid_purchase": float(self.invalid_purchase),
        }


@dataclass(frozen=True, slots=True)
class AgentRewardBreakdown:
    """Recompensa híbrida que recibe un agente en una transición."""

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
    closed_operation_roi: Decimal | None = None,
    extra_hold_days: int = 0,
    constraint_violation_ratio: Decimal = Decimal("0"),
    config: CooperativeRewardConfig | None = None,
) -> CooperativeRewardBreakdown:
    """Calcula la recompensa común.

    ``closed_operation_roi`` solo existe si se ha cerrado una posición. Se
    limita a ``[-1, 1]`` antes de aplicar su peso para que un caso excepcional
    no monopolice el aprendizaje. ``extra_hold_days`` cuenta únicamente los
    días posteriores al bloqueo de intercambio habitual. La infracción se
    expresa como proporción de límites incumplidos y se limita a ``[0, 1]``.
    """

    reward_config = config or CooperativeRewardConfig()
    if extra_hold_days < 0:
        raise ValueError("extra_hold_days must be non-negative")

    if closed_operation_roi is not None:
        roi = _clip(closed_operation_roi, lower=Decimal("-1"), upper=Decimal("1"))
        return CooperativeRewardBreakdown(
            closed_operation_roi=reward_config.roi_weight * roi,
            extra_hold_days=-reward_config.extra_hold_day_penalty * Decimal(extra_hold_days),
            invalid_purchase=Decimal("0"),
        )

    violation_ratio = _clip(
        constraint_violation_ratio,
        lower=Decimal("0"),
        upper=Decimal("1"),
    )
    return CooperativeRewardBreakdown(
        closed_operation_roi=Decimal("0"),
        extra_hold_days=Decimal("0"),
        invalid_purchase=-reward_config.constraint_violation_penalty * violation_ratio,
    )


def calculate_agent_reward_breakdowns(
    *,
    agents: tuple[str, ...],
    shared_breakdown: CooperativeRewardBreakdown,
    closed_operation_roi: Decimal | None = None,
    scout_marked_closed_item: bool = False,
    missed_opportunity_roi: Decimal | None = None,
    missed_opportunity_affordable: bool = False,
    trader_declined_viable_purchase: bool = False,
    portfolio_rejected_viable_purchase: bool = False,
    trader_underinvestment_ratio: Decimal = Decimal("0"),
    trader_proposed_invalid_purchase: bool = False,
    portfolio_approved_invalid_purchase: bool = False,
    constraint_violation_ratio: Decimal = Decimal("0"),
    hybrid_config: HybridRewardConfig | None = None,
) -> dict[str, AgentRewardBreakdown]:
    """Devuelve la recompensa híbrida para Scout, Trader y Portfolio.

    Las penalizaciones locales se producen solo cuando el resultado permite
    atribuir una responsabilidad concreta. Una pérdida de una operación marcada
    afecta a todo el equipo mediante la parte común y, además, a Scout. Una
    oportunidad omitida se penaliza solo si, al vencer su horizonte, resultó
    rentable y había saldo suficiente al detectarla.
    """

    mix_config = hybrid_config or HybridRewardConfig()
    violation_ratio = _clip(
        constraint_violation_ratio,
        lower=Decimal("0"),
        upper=Decimal("1"),
    )
    underinvestment = _clip(
        trader_underinvestment_ratio,
        lower=Decimal("0"),
        upper=Decimal("1"),
    )
    signals = {
        "scout": _scout_signal(
            closed_operation_roi=closed_operation_roi,
            scout_marked_closed_item=scout_marked_closed_item,
            missed_opportunity_roi=missed_opportunity_roi,
            missed_opportunity_affordable=missed_opportunity_affordable,
        ),
        "trader": _trader_signal(
            missed_opportunity_roi=missed_opportunity_roi,
            trader_declined_viable_purchase=trader_declined_viable_purchase,
            trader_underinvestment_ratio=underinvestment,
            trader_proposed_invalid_purchase=trader_proposed_invalid_purchase,
            constraint_violation_ratio=violation_ratio,
        ),
        "portfolio": _portfolio_signal(
            portfolio_approved_invalid_purchase=portfolio_approved_invalid_purchase,
            missed_opportunity_roi=missed_opportunity_roi,
            portfolio_rejected_viable_purchase=portfolio_rejected_viable_purchase,
            constraint_violation_ratio=violation_ratio,
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


def shared_reward_map(
    agents: tuple[str, ...],
    breakdown: CooperativeRewardBreakdown,
) -> dict[str, float]:
    """Return the common component alone, useful for diagnostics."""

    return {agent_id: float(breakdown.total) for agent_id in agents}


def reward_info(breakdown: CooperativeRewardBreakdown) -> Mapping[str, float]:
    return breakdown.as_float_dict()


def agent_reward_info(breakdown: AgentRewardBreakdown) -> Mapping[str, float]:
    return breakdown.as_float_dict()


def _scout_signal(
    *,
    closed_operation_roi: Decimal | None,
    scout_marked_closed_item: bool,
    missed_opportunity_roi: Decimal | None,
    missed_opportunity_affordable: bool,
) -> Decimal:
    if (
        closed_operation_roi is not None
        and scout_marked_closed_item
        and closed_operation_roi < 0
    ):
        return _clip(closed_operation_roi, lower=Decimal("-1"), upper=Decimal("1"))
    if (
        missed_opportunity_roi is not None
        and missed_opportunity_affordable
        and missed_opportunity_roi > 0
    ):
        return -_clip(missed_opportunity_roi, lower=Decimal("0"), upper=Decimal("1"))
    return Decimal("0")


def _trader_signal(
    *,
    missed_opportunity_roi: Decimal | None,
    trader_declined_viable_purchase: bool,
    trader_underinvestment_ratio: Decimal,
    trader_proposed_invalid_purchase: bool,
    constraint_violation_ratio: Decimal,
) -> Decimal:
    if trader_proposed_invalid_purchase:
        return -constraint_violation_ratio
    if (
        trader_declined_viable_purchase
        and missed_opportunity_roi is not None
        and missed_opportunity_roi > 0
    ):
        return -_clip(missed_opportunity_roi, lower=Decimal("0"), upper=Decimal("1"))
    if trader_underinvestment_ratio > 0:
        return -trader_underinvestment_ratio
    return Decimal("0")


def _portfolio_signal(
    *,
    portfolio_approved_invalid_purchase: bool,
    missed_opportunity_roi: Decimal | None,
    portfolio_rejected_viable_purchase: bool,
    constraint_violation_ratio: Decimal,
) -> Decimal:
    if portfolio_approved_invalid_purchase:
        return -constraint_violation_ratio
    if (
        portfolio_rejected_viable_purchase
        and missed_opportunity_roi is not None
        and missed_opportunity_roi > 0
    ):
        return -_clip(missed_opportunity_roi, lower=Decimal("0"), upper=Decimal("1"))
    return Decimal("0")


def _clip(value: Decimal, *, lower: Decimal, upper: Decimal) -> Decimal:
    return max(lower, min(upper, value))

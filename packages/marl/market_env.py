"""Minimal parallel MARL market environment.

This is intentionally a small PettingZoo-compatible core, not a dependency-bound wrapper yet.
It gives Scout, Trader and Portfolio stable observations/actions while reusing the deterministic
portfolio simulator and risk rules.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from packages.marl.rewards import (
    CooperativeRewardBreakdown,
    CooperativeRewardConfig,
    calculate_cooperative_reward,
    reward_info,
    shared_reward_map,
)
from packages.simulation import (
    STEAM,
    PortfolioRiskConfig,
    PortfolioSimulator,
    RiskCandidate,
    default_portfolio_risk_config,
    evaluate_portfolio_risk,
)

AGENT_IDS = ("scout", "trader", "portfolio")
ActionMap = Mapping[str, int]
ObservationMap = dict[str, dict[str, float]]
InfoMap = dict[str, dict[str, Any]]
ActionMaskMap = dict[str, tuple[int, ...]]
EMPTY_REWARD_BREAKDOWN = CooperativeRewardBreakdown(
    realized_profit=Decimal("0"),
    executed_return=Decimal("0"),
    inactivity=Decimal("0"),
    risk_violation=Decimal("0"),
    drawdown=Decimal("0"),
    blocked_capital=Decimal("0"),
    volatility=Decimal("0"),
)


@dataclass(frozen=True, slots=True)
class AgentSpec:
    agent_id: str
    role: str
    observation_fields: tuple[str, ...]
    action_space: dict[int, str]
    executes_trades: bool


AGENT_SPECS = {
    "scout": AgentSpec(
        agent_id="scout",
        role="Detecta oportunidades y marca candidatos; no ejecuta operaciones.",
        observation_fields=(
            "buy_price_eur",
            "current_return",
            "supervised_probability",
            "available_quantity",
        ),
        action_space={0: "ignore", 1: "mark_opportunity"},
        executes_trades=False,
    ),
    "trader": AgentSpec(
        agent_id="trader",
        role="Decide mantener o comprar una unidad cuando Scout y Portfolio lo permiten.",
        observation_fields=(
            "buy_price_eur",
            "current_exit_net_eur",
            "current_return",
            "cash_available_ratio",
        ),
        action_space={0: "hold", 1: "buy_one"},
        executes_trades=True,
    ),
    "portfolio": AgentSpec(
        agent_id="portfolio",
        role="Aprueba o rechaza candidatos usando exposicion, liquidez y capital bloqueado.",
        observation_fields=(
            "cash_available_ratio",
            "cash_after_candidate_ratio",
            "blocked_capital_ratio",
            "candidate_position_ratio",
            "violation_count",
            "warning_count",
        ),
        action_space={0: "reject", 1: "approve"},
        executes_trades=False,
    ),
}


@dataclass(frozen=True, slots=True)
class MarketEpisodeStep:
    item_id: str
    representation_name: str
    observed_day: date
    buy_price_eur: Decimal
    current_exit_net_eur: Decimal
    current_return: Decimal
    steam_sell_price_eur: Decimal | None = None
    buff_buy_order_price_eur: Decimal | None = None
    available_quantity: int | None = None
    supervised_probability: Decimal | None = None
    volatility: Decimal | None = None

    @classmethod
    def from_mapping(cls, row: Mapping[str, Any]) -> MarketEpisodeStep:
        return cls(
            item_id=_required_text(row, "item_id"),
            representation_name=_required_text(row, "representation_name"),
            observed_day=_date_value(row["observed_day"]),
            buy_price_eur=_positive_decimal(row["buy_price_eur"], "buy_price_eur"),
            current_exit_net_eur=_decimal(row["current_exit_net_eur"]),
            current_return=_decimal(row["current_return"]),
            steam_sell_price_eur=_optional_decimal(row.get("steam_sell_price_eur")),
            buff_buy_order_price_eur=_optional_decimal(row.get("buff_buy_order_price_eur")),
            available_quantity=_optional_int(row.get("available_quantity")),
            supervised_probability=_optional_decimal(row.get("supervised_probability")),
            volatility=_optional_decimal(row.get("volatility")),
        )


class MarketMARLEnvironment:
    """Small deterministic parallel environment for the first MARL integration tests."""

    agent_specs = AGENT_SPECS
    action_spaces = {agent_id: spec.action_space for agent_id, spec in AGENT_SPECS.items()}
    observation_spaces = {
        agent_id: spec.observation_fields for agent_id, spec in AGENT_SPECS.items()
    }

    def __init__(
        self,
        episode_steps: Sequence[MarketEpisodeStep],
        *,
        initial_cash_eur: Decimal = Decimal("1000"),
        risk_config: PortfolioRiskConfig | None = None,
        reward_config: CooperativeRewardConfig | None = None,
    ) -> None:
        if not episode_steps:
            raise ValueError("episode_steps cannot be empty")
        self._episode_steps = tuple(sorted(episode_steps, key=lambda step: step.observed_day))
        self._initial_cash_eur = initial_cash_eur
        self._risk_config = risk_config or default_portfolio_risk_config()
        self._reward_config = reward_config or CooperativeRewardConfig()
        self.agents = list(AGENT_IDS)
        self._simulator = PortfolioSimulator(initial_cash_eur=initial_cash_eur)
        self._index = 0
        self._terminated = False

    @property
    def simulator(self) -> PortfolioSimulator:
        return self._simulator

    def reset(self) -> tuple[ObservationMap, InfoMap]:
        self.agents = list(AGENT_IDS)
        self._simulator = PortfolioSimulator(initial_cash_eur=self._initial_cash_eur)
        self._index = 0
        self._terminated = False
        return self._observations(), self._infos(executed_trade=False, reward=Decimal("0"))

    def step(
        self,
        actions: ActionMap,
    ) -> tuple[ObservationMap, dict[str, float], dict[str, bool], dict[str, bool], InfoMap]:
        if self._terminated:
            return {}, {}, {}, {}, {}

        normalized_actions = _validated_actions(actions)
        current = self._current_step()
        candidate = _risk_candidate(current)
        risk = evaluate_portfolio_risk(
            self._simulator,
            as_of=current.observed_day,
            config=self._risk_config,
            candidate=candidate,
        )
        action_masks = _action_masks_from_allowed(risk.candidate_allowed)
        wanted_buy = _wants_buy(normalized_actions)
        executed_trade = wanted_buy and risk.candidate_allowed
        before_metrics = self._simulator.metrics(as_of=current.observed_day)
        if executed_trade:
            self._simulator.buy(
                item_id=current.item_id,
                item_name=current.representation_name,
                buy_platform=STEAM,
                buy_price=current.buy_price_eur,
                buy_currency="EUR",
                purchased_at=current.observed_day,
            )
        after_metrics = self._simulator.metrics(as_of=current.observed_day)
        reward_breakdown = calculate_cooperative_reward(
            before_metrics=before_metrics,
            after_metrics=after_metrics,
            executed_trade=executed_trade,
            opportunity_available=current.current_return > 0 and risk.candidate_allowed,
            risk_violations=risk.violations if wanted_buy else (),
            opportunity_return=current.current_return,
            candidate_volatility=current.volatility if executed_trade else None,
            config=self._reward_config,
        )

        self._index += 1
        self._terminated = self._index >= len(self._episode_steps)
        observations = {} if self._terminated else self._observations()
        rewards = shared_reward_map(AGENT_IDS, reward_breakdown)
        terminations = {agent_id: self._terminated for agent_id in AGENT_IDS}
        truncations = {agent_id: False for agent_id in AGENT_IDS}
        infos = self._infos(
            step=current,
            action_masks=action_masks,
            executed_trade=executed_trade,
            reward=reward_breakdown.total,
            reward_breakdown=reward_breakdown,
            risk_violations=risk.violations,
        )
        if self._terminated:
            self.agents = []
        return observations, rewards, terminations, truncations, infos

    def action_masks(self) -> ActionMaskMap:
        if self._terminated:
            return {}

        current = self._current_step()
        risk = evaluate_portfolio_risk(
            self._simulator,
            as_of=current.observed_day,
            config=self._risk_config,
            candidate=_risk_candidate(current),
        )
        candidate_allowed = int(risk.candidate_allowed)
        return _action_masks_from_allowed(bool(candidate_allowed))

    def _observations(self) -> ObservationMap:
        current = self._current_step()
        risk = evaluate_portfolio_risk(
            self._simulator,
            as_of=current.observed_day,
            config=self._risk_config,
            candidate=_risk_candidate(current),
        )
        base = {
            "buy_price_eur": _float(current.buy_price_eur),
            "current_exit_net_eur": _float(current.current_exit_net_eur),
            "current_return": _float(current.current_return),
            "steam_sell_price_eur": _float(current.steam_sell_price_eur),
            "buff_buy_order_price_eur": _float(current.buff_buy_order_price_eur),
            "available_quantity": float(current.available_quantity or 0),
            "supervised_probability": _float(current.supervised_probability),
        }
        portfolio_features = {
            key: _float(value)
            for key, value in risk.observation.items()
        }
        return {
            "scout": {
                key: base[key]
                for key in self.observation_spaces["scout"]
            },
            "trader": {
                **{
                    key: base[key]
                    for key in self.observation_spaces["trader"]
                    if key in base
                },
                "cash_available_ratio": portfolio_features["cash_available_ratio"],
            },
            "portfolio": {
                key: portfolio_features[key]
                for key in self.observation_spaces["portfolio"]
            },
        }

    def _infos(
        self,
        *,
        step: MarketEpisodeStep | None = None,
        action_masks: ActionMaskMap | None = None,
        executed_trade: bool,
        reward: Decimal = Decimal("0"),
        reward_breakdown: CooperativeRewardBreakdown | None = None,
        risk_violations: tuple[str, ...] = (),
    ) -> InfoMap:
        resolved_step = step or self._episode_steps[min(self._index, len(self._episode_steps) - 1)]
        resolved_action_masks = action_masks if action_masks is not None else self.action_masks()
        payload = {
            "item_id": resolved_step.item_id,
            "representation_name": resolved_step.representation_name,
            "observed_day": resolved_step.observed_day.isoformat(),
            "executed_trade": executed_trade,
            "reward": float(reward),
            "reward_breakdown": reward_info(reward_breakdown or EMPTY_REWARD_BREAKDOWN),
            "risk_violations": risk_violations,
        }
        return {
            agent_id: {
                **payload,
                "action_mask": resolved_action_masks.get(agent_id, ()),
            }
            for agent_id in AGENT_IDS
        }

    def _current_step(self) -> MarketEpisodeStep:
        return self._episode_steps[self._index]


def _wants_buy(actions: ActionMap) -> bool:
    return (
        actions.get("scout", 0) == 1
        and actions.get("trader", 0) == 1
        and actions.get("portfolio", 0) == 1
    )


def _action_masks_from_allowed(candidate_allowed: bool) -> ActionMaskMap:
    buy_allowed = int(candidate_allowed)
    return {
        "scout": (1, 1),
        "trader": (1, buy_allowed),
        "portfolio": (1, buy_allowed),
    }


def _validated_actions(actions: ActionMap) -> dict[str, int]:
    unknown_agents = sorted(set(actions) - set(AGENT_IDS))
    if unknown_agents:
        raise ValueError(f"unknown agent action(s): {', '.join(unknown_agents)}")

    normalized = {agent_id: int(actions.get(agent_id, 0)) for agent_id in AGENT_IDS}
    invalid = [
        f"{agent_id}={action}"
        for agent_id, action in normalized.items()
        if action not in AGENT_SPECS[agent_id].action_space
    ]
    if invalid:
        raise ValueError(f"invalid action(s): {', '.join(invalid)}")
    return normalized


def _risk_candidate(step: MarketEpisodeStep) -> RiskCandidate:
    return RiskCandidate(
        item_id=step.item_id,
        buy_platform=STEAM,
        buy_value_eur=step.buy_price_eur,
        available_quantity=step.available_quantity,
        volatility=step.volatility,
    )


def _required_text(row: Mapping[str, Any], key: str) -> str:
    text = str(row.get(key) or "").strip()
    if not text:
        raise ValueError(f"{key} cannot be empty")
    return text


def _date_value(value: Any) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    return date.fromisoformat(str(value))


def _positive_decimal(value: Any, field_name: str) -> Decimal:
    parsed = _decimal(value)
    if parsed <= 0:
        raise ValueError(f"{field_name} must be greater than zero")
    return parsed


def _decimal(value: Any) -> Decimal:
    return Decimal(str(value))


def _optional_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def _float(value: Decimal | None) -> float:
    return float(value or Decimal("0"))

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
    BUFF163,
    STEAM,
    MarketEconomicsConfig,
    PortfolioRiskConfig,
    PortfolioSimulator,
    RiskCandidate,
    default_portfolio_risk_config,
    effective_cash_value,
    evaluate_portfolio_risk,
    return_ratio,
)

AGENT_IDS = ("scout", "trader", "portfolio")
PRICE_TYPE_LISTING = "listing"
PRICE_TYPE_BUY_ORDER = "buy_order"
CASH_DESTINATION_REINVEST = "reinvest"
CASH_DESTINATION_CASHOUT = "cashout"
ActionMap = Mapping[str, int]
ObservationMap = dict[str, dict[str, float]]
CentralStateMap = dict[str, float]
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
            "buy_platform_is_steam",
            "buy_platform_is_buff",
            "buy_price_is_listing",
            "buy_price_is_buy_order",
            "sell_platform_is_steam",
            "sell_platform_is_buff",
            "sell_price_is_listing",
            "sell_price_is_buy_order",
            "buy_price_eur",
            "current_return",
            "current_cash_return",
            "supervised_probability",
            "supervised_probability_available",
            "available_quantity",
        ),
        action_space={0: "ignore", 1: "mark_opportunity"},
        executes_trades=False,
    ),
    "trader": AgentSpec(
        agent_id="trader",
        role="Decide mantener o comprar una unidad cuando Scout y Portfolio lo permiten.",
        observation_fields=(
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
            "supervised_probability",
            "supervised_probability_available",
            "violation_count",
            "warning_count",
        ),
        action_space={0: "reject", 1: "approve"},
        executes_trades=False,
    ),
}

CENTRAL_STATE_FIELDS = (
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
    "cash_destination_is_reinvest",
    "cash_destination_is_cashout",
    "supervised_probability",
    "supervised_probability_available",
    "available_quantity",
    "cash_available_ratio",
    "cash_after_candidate_ratio",
    "blocked_capital_ratio",
    "candidate_position_ratio",
    "violation_count",
    "warning_count",
)


@dataclass(frozen=True, slots=True)
class MarketEpisodeStep:
    item_id: str
    representation_name: str
    observed_day: date
    buy_price_eur: Decimal
    current_exit_net_eur: Decimal
    current_return: Decimal
    buy_platform: str = STEAM
    buy_currency: str = "EUR"
    buy_price_type: str = PRICE_TYPE_LISTING
    sell_platform: str = STEAM
    sell_price_type: str = PRICE_TYPE_LISTING
    cash_destination: str = CASH_DESTINATION_REINVEST
    current_cash_value_eur: Decimal | None = None
    current_cash_return: Decimal | None = None
    steam_sell_price_eur: Decimal | None = None
    buff_buy_order_price_eur: Decimal | None = None
    available_quantity: int | None = None
    supervised_probability: Decimal | None = None
    supervised_model_version: str | None = None
    volatility: Decimal | None = None

    @classmethod
    def from_mapping(cls, row: Mapping[str, Any]) -> MarketEpisodeStep:
        buy_price_eur = _positive_decimal(row["buy_price_eur"], "buy_price_eur")
        current_exit_net_eur = _decimal(row["current_exit_net_eur"])
        current_cash_value_eur = _optional_decimal(row.get("current_cash_value_eur"))
        current_cash_return = (
            _optional_decimal(row.get("current_cash_return"))
            if current_cash_value_eur is not None
            else None
        )
        return cls(
            item_id=_required_text(row, "item_id"),
            representation_name=_required_text(row, "representation_name"),
            observed_day=_date_value(row["observed_day"]),
            buy_price_eur=buy_price_eur,
            current_exit_net_eur=current_exit_net_eur,
            current_return=_decimal(row["current_return"]),
            buy_platform=_platform_text(row.get("buy_platform") or STEAM),
            buy_currency=str(row.get("buy_currency") or "EUR").upper(),
            buy_price_type=_price_type(row.get("buy_price_type") or row.get("buy_mode")),
            sell_platform=_platform_text(row.get("sell_platform") or STEAM),
            sell_price_type=_price_type(row.get("sell_price_type") or row.get("sell_mode")),
            cash_destination=_cash_destination(row.get("cash_destination")),
            current_cash_value_eur=current_cash_value_eur,
            current_cash_return=current_cash_return
            or (
                return_ratio(current_cash_value_eur - buy_price_eur, buy_price_eur)
                if current_cash_value_eur is not None
                else None
            ),
            steam_sell_price_eur=_optional_decimal(row.get("steam_sell_price_eur")),
            buff_buy_order_price_eur=_optional_decimal(row.get("buff_buy_order_price_eur")),
            available_quantity=_optional_int(row.get("available_quantity")),
            supervised_probability=_optional_decimal(row.get("supervised_probability")),
            supervised_model_version=_optional_text(row.get("supervised_model_version")),
            volatility=_optional_decimal(row.get("volatility")),
        )

    @property
    def route_label(self) -> str:
        return (
            f"{self.buy_platform} {self.buy_price_type} -> "
            f"{self.sell_platform} {self.sell_price_type}"
        )

    @property
    def exit_balance_platform(self) -> str:
        return self.sell_platform


class MarketMARLEnvironment:
    """Small deterministic parallel environment for the first MARL integration tests."""

    agent_specs = AGENT_SPECS
    central_state_fields = CENTRAL_STATE_FIELDS
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
        include_supervised_probability: bool = True,
    ) -> None:
        if not episode_steps:
            raise ValueError("episode_steps cannot be empty")
        self._episode_steps = tuple(sorted(episode_steps, key=lambda step: step.observed_day))
        self._initial_cash_eur = initial_cash_eur
        self._risk_config = risk_config or default_portfolio_risk_config()
        self._reward_config = reward_config or CooperativeRewardConfig()
        self._include_supervised_probability = include_supervised_probability
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
                buy_platform=current.buy_platform,
                buy_price=current.buy_price_eur,
                buy_currency=current.buy_currency,
                purchased_at=current.observed_day,
                metadata={
                    "route_label": current.route_label,
                    "buy_price_type": current.buy_price_type,
                    "sell_platform": current.sell_platform,
                    "sell_price_type": current.sell_price_type,
                    "cash_destination": current.cash_destination,
                },
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

    def central_state(self) -> CentralStateMap:
        if self._terminated:
            return {}
        return self._central_state_for(self._current_step())

    def _observations(self) -> ObservationMap:
        current = self._current_step()
        risk = self._risk_snapshot(current)
        features = _state_features(
            current,
            risk_observation=risk.observation,
            config=self._simulator.config,
            include_supervised_probability=self._include_supervised_probability,
        )
        return {
            "scout": {
                key: features[key]
                for key in self.observation_spaces["scout"]
            },
            "trader": {
                key: features[key]
                for key in self.observation_spaces["trader"]
            },
            "portfolio": {
                key: features[key]
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
            "route_label": resolved_step.route_label,
            "route_selection": "candidate",
            "buy_platform": resolved_step.buy_platform,
            "buy_price_type": resolved_step.buy_price_type,
            "sell_platform": resolved_step.sell_platform,
            "sell_price_type": resolved_step.sell_price_type,
            "exit_balance_platform": resolved_step.exit_balance_platform,
            "cash_destination": resolved_step.cash_destination,
            "cashflow": _cashflow_info(resolved_step, self._simulator.config),
            "central_state_fields": self.central_state_fields,
            "central_state": self._central_state_for(resolved_step),
            "supervised_probability_enabled": self._include_supervised_probability,
            "supervised_probability_available": bool(
                _supervised_probability_available(
                    resolved_step,
                    self._include_supervised_probability,
                )
            ),
            "supervised_model_version": resolved_step.supervised_model_version,
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

    def _risk_snapshot(self, step: MarketEpisodeStep) -> Any:
        return evaluate_portfolio_risk(
            self._simulator,
            as_of=step.observed_day,
            config=self._risk_config,
            candidate=_risk_candidate(step),
        )

    def _central_state_for(self, step: MarketEpisodeStep) -> CentralStateMap:
        risk = self._risk_snapshot(step)
        features = _state_features(
            step,
            risk_observation=risk.observation,
            config=self._simulator.config,
            include_supervised_probability=self._include_supervised_probability,
        )
        return {
            key: features[key]
            for key in self.central_state_fields
        }


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
        buy_platform=step.buy_platform,
        buy_value_eur=step.buy_price_eur,
        available_quantity=step.available_quantity,
        volatility=step.volatility,
    )


def _state_features(
    step: MarketEpisodeStep,
    *,
    risk_observation: Mapping[str, Decimal],
    config: MarketEconomicsConfig,
    include_supervised_probability: bool,
) -> dict[str, float]:
    features = {
        "buy_price_eur": _float(step.buy_price_eur),
        "buy_platform_is_steam": _platform_flag(step.buy_platform, STEAM),
        "buy_platform_is_buff": _platform_flag(step.buy_platform, BUFF163),
        "buy_price_is_listing": _price_type_flag(
            step.buy_price_type,
            PRICE_TYPE_LISTING,
        ),
        "buy_price_is_buy_order": _price_type_flag(
            step.buy_price_type,
            PRICE_TYPE_BUY_ORDER,
        ),
        "sell_platform_is_steam": _platform_flag(step.sell_platform, STEAM),
        "sell_platform_is_buff": _platform_flag(step.sell_platform, BUFF163),
        "sell_price_is_listing": _price_type_flag(
            step.sell_price_type,
            PRICE_TYPE_LISTING,
        ),
        "sell_price_is_buy_order": _price_type_flag(
            step.sell_price_type,
            PRICE_TYPE_BUY_ORDER,
        ),
        "current_exit_net_eur": _float(step.current_exit_net_eur),
        "current_return": _float(step.current_return),
        "current_cash_value_eur": _float(_effective_cash_value(step, config)),
        "current_cash_return": _float(_effective_cash_return(step, config)),
        "cash_destination_is_reinvest": _cash_destination_flag(
            step.cash_destination,
            CASH_DESTINATION_REINVEST,
        ),
        "cash_destination_is_cashout": _cash_destination_flag(
            step.cash_destination,
            CASH_DESTINATION_CASHOUT,
        ),
        "steam_sell_price_eur": _float(step.steam_sell_price_eur),
        "buff_buy_order_price_eur": _float(step.buff_buy_order_price_eur),
        "available_quantity": float(step.available_quantity or 0),
        "supervised_probability": _float(
            _supervised_probability(step, include_supervised_probability)
        ),
        "supervised_probability_available": _supervised_probability_available(
            step,
            include_supervised_probability,
        ),
    }
    features.update({key: _float(value) for key, value in risk_observation.items()})
    return features


def _required_text(row: Mapping[str, Any], key: str) -> str:
    text = str(row.get(key) or "").strip()
    if not text:
        raise ValueError(f"{key} cannot be empty")
    return text


def _platform_text(value: Any) -> str:
    text = str(value or "").strip().upper()
    if not text:
        raise ValueError("buy_platform cannot be empty")
    return text


def _platform_flag(platform: str, expected: str) -> float:
    return 1.0 if platform.upper() == expected else 0.0


def _price_type(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return PRICE_TYPE_LISTING
    if "buy order" in text or "highest buy order" in text or text == PRICE_TYPE_BUY_ORDER:
        return PRICE_TYPE_BUY_ORDER
    if "lowest price" in text or "listing" in text or text == PRICE_TYPE_LISTING:
        return PRICE_TYPE_LISTING
    raise ValueError(f"unknown price type: {value}")


def _price_type_flag(price_type: str, expected: str) -> float:
    return 1.0 if price_type == expected else 0.0


def _cash_destination(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return CASH_DESTINATION_REINVEST
    if text in {CASH_DESTINATION_REINVEST, "platform_balance", "balance"}:
        return CASH_DESTINATION_REINVEST
    if text in {CASH_DESTINATION_CASHOUT, "cash_out", "withdraw", "withdrawal"}:
        return CASH_DESTINATION_CASHOUT
    raise ValueError(f"unknown cash destination: {value}")


def _cash_destination_flag(cash_destination: str, expected: str) -> float:
    return 1.0 if cash_destination == expected else 0.0


def _cashflow_info(step: MarketEpisodeStep, config: MarketEconomicsConfig) -> dict[str, Any]:
    cash_value = _effective_cash_value(step, config)
    cash_return = _effective_cash_return(step, config)
    return {
        "buy_value_eur": float(step.buy_price_eur),
        "exit_balance_platform": step.exit_balance_platform,
        "exit_balance_value_eur": float(step.current_exit_net_eur),
        "effective_cash_value_eur": float(cash_value),
        "effective_cash_return": float(cash_return),
        "cash_destination": step.cash_destination,
    }


def _effective_cash_value(step: MarketEpisodeStep, config: MarketEconomicsConfig) -> Decimal:
    if step.current_cash_value_eur is not None:
        return step.current_cash_value_eur
    if step.cash_destination == CASH_DESTINATION_CASHOUT:
        return effective_cash_value(
            step.current_exit_net_eur,
            platform=step.exit_balance_platform,
            config=config,
        )
    return step.current_exit_net_eur


def _effective_cash_return(step: MarketEpisodeStep, config: MarketEconomicsConfig) -> Decimal:
    if step.current_cash_return is not None:
        return step.current_cash_return
    return return_ratio(
        _effective_cash_value(step, config) - step.buy_price_eur,
        step.buy_price_eur,
    )


def _supervised_probability(
    step: MarketEpisodeStep,
    include_supervised_probability: bool,
) -> Decimal | None:
    if not include_supervised_probability:
        return None
    return step.supervised_probability


def _supervised_probability_available(
    step: MarketEpisodeStep,
    include_supervised_probability: bool,
) -> float:
    return float(include_supervised_probability and step.supervised_probability is not None)


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


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _float(value: Decimal | None) -> float:
    return float(value or Decimal("0"))

"""Evaluación única de la prueba temporal con políticas y baselines homogéneos."""

from __future__ import annotations

import json
import random
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

import numpy as np

from packages.marl.ctde_training import CTDEPolicy
from packages.marl.episodes import MarketEpisodeSource, load_market_episode_source
from packages.marl.market_env import AllocationTargetConfig, MarketMARLEnvironment
from packages.marl.rewards import CooperativeRewardConfig, HybridRewardConfig
from packages.marl.single_agent_training import SingleAgentPolicy
from packages.simulation import PortfolioRiskConfig

ActionPolicy = Callable[[MarketMARLEnvironment, dict[str, dict[str, float]]], dict[str, int]]


@dataclass(frozen=True, slots=True)
class FinalEvaluationConfig:
    dataset_dir: Path
    asset_ids: tuple[str, ...]
    initial_cash_eur: Decimal
    risk_config: PortfolioRiskConfig
    reward_config: CooperativeRewardConfig
    hybrid_reward_config: HybridRewardConfig
    allocation_config: AllocationTargetConfig
    episode_days: int = 14
    max_steps_per_episode: int = 2_000
    episodes: int = 8
    test_seed: int = 20_007


def evaluate_final(
    config: FinalEvaluationConfig,
    *,
    marl_policies: dict[str, CTDEPolicy],
    single_agent_policies: dict[str, SingleAgentPolicy],
) -> dict[str, Any]:
    """Evalúa todas las alternativas sobre las mismas ventanas de prueba."""

    source = load_market_episode_source(
        config.dataset_dir,
        split="test",
        item_ids=frozenset(config.asset_ids),
    )
    policies: dict[str, dict[str, ActionPolicy]] = {
        "marl": {seed: _marl_actions(policy) for seed, policy in marl_policies.items()},
        "single_agent": {
            seed: _single_agent_actions(policy) for seed, policy in single_agent_policies.items()
        },
        "cash": {"deterministic": _cash_actions},
        "positive_margin": {"deterministic": _positive_margin_actions},
    }
    result: dict[str, Any] = {
        "schema_version": "csflipper_marl_final_test.v1",
        "split": "test",
        "test_seed": config.test_seed,
        "episodes": config.episodes,
        "asset_count": len(config.asset_ids),
        "initial_cash_eur": float(config.initial_cash_eur),
        "policies": {},
    }
    for policy_name, replicas in policies.items():
        runs = [
            _evaluate_policy(source, action_policy, config=config)
            for action_policy in replicas.values()
        ]
        result["policies"][policy_name] = {
            "replicas": list(replicas),
            "runs": runs,
            "summary": _summary(runs),
        }
    return result


def write_final_evaluation(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")


def _evaluate_policy(
    source: MarketEpisodeSource,
    action_policy: ActionPolicy,
    *,
    config: FinalEvaluationConfig,
) -> dict[str, float | int]:
    rng = random.Random(config.test_seed)
    episodes = [
        _evaluate_episode(
            source.sample_window(
                days=config.episode_days,
                rng=rng,
                max_steps=config.max_steps_per_episode,
            ),
            action_policy,
            config=config,
        )
        for _ in range(config.episodes)
    ]
    return _summary(episodes)


def _evaluate_episode(
    steps: tuple[Any, ...],
    action_policy: ActionPolicy,
    *,
    config: FinalEvaluationConfig,
) -> dict[str, float | int]:
    env = MarketMARLEnvironment(
        steps,
        initial_cash_eur=config.initial_cash_eur,
        risk_config=config.risk_config,
        reward_config=config.reward_config,
        hybrid_reward_config=config.hybrid_reward_config,
        allocation_config=config.allocation_config,
    )
    observations, _infos = env.reset()
    purchases = 0
    sales = 0
    restriction_rejections = 0
    while env.agents:
        actions = action_policy(env, observations)
        observations, _rewards, _terminations, _truncations, infos = env.step(actions)
        info = infos["scout"]
        purchases += int(info["executed_buy"])
        sales += int(info["executed_sale"])
        restriction_rejections += int(bool(info["risk_violations"]))
    metrics = env.simulator.metrics(as_of=steps[-1].observed_day)
    return {
        "equity_return": float(
            (metrics.equity_eur - config.initial_cash_eur) / config.initial_cash_eur
        ),
        "final_equity_eur": float(metrics.equity_eur),
        "final_cash_eur": float(metrics.cash_available_eur),
        "realized_profit_eur": float(metrics.realized_profit_eur),
        "capital_blocked_eur": float(metrics.capital_blocked_eur),
        "open_positions": int(metrics.open_positions),
        "closed_operations": int(metrics.closed_positions),
        "drawdown_ratio": float(metrics.drawdown_ratio),
        "purchases": purchases,
        "sales": sales,
        "restriction_rejections": restriction_rejections,
    }


def _summary(runs: list[dict[str, float | int]]) -> dict[str, float | int]:
    summary: dict[str, float | int] = {"replicas": len(runs)}
    for key in runs[0]:
        values = [float(run[key]) for run in runs]
        summary[f"mean_{key}"] = float(np.mean(values))
        summary[f"min_{key}"] = float(np.min(values))
        summary[f"max_{key}"] = float(np.max(values))
    return summary


def _marl_actions(policy: CTDEPolicy) -> ActionPolicy:
    def select(
        env: MarketMARLEnvironment, observations: dict[str, dict[str, float]]
    ) -> dict[str, int]:
        return policy.select_actions(observations, action_masks=env.action_masks())

    return select


def _single_agent_actions(policy: SingleAgentPolicy) -> ActionPolicy:
    def select(
        env: MarketMARLEnvironment, _observations: dict[str, dict[str, float]]
    ) -> dict[str, int]:
        return policy.select_actions(env.central_state(), env.action_masks())

    return select


def _cash_actions(
    _env: MarketMARLEnvironment,
    _observations: dict[str, dict[str, float]],
) -> dict[str, int]:
    return {"scout": 0, "trader": 0, "portfolio": 0}


def _positive_margin_actions(
    env: MarketMARLEnvironment,
    observations: dict[str, dict[str, float]],
) -> dict[str, int]:
    masks = env.action_masks()
    trader = observations["trader"]
    if trader["matching_sellable_positions"] > 0 and masks["trader"][2]:
        return {"scout": 0, "trader": 2, "portfolio": 1}
    if (
        observations["scout"]["current_return"] > 0
        and masks["scout"][1]
        and masks["trader"][1]
        and masks["portfolio"][1]
    ):
        return {"scout": 1, "trader": 1, "portfolio": 1}
    return _cash_actions(env, observations)

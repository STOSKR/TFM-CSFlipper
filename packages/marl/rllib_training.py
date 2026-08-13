"""RLlib training helpers for the CSFlipper MARL environment."""

# mypy: disable-error-code=no-untyped-call

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
from gymnasium import spaces
from ray.rllib.algorithms.ppo import PPOConfig
from ray.rllib.env.multi_agent_env import MultiAgentEnv
from ray.rllib.policy.policy import PolicySpec
from ray.tune.registry import register_env

from packages.marl.episodes import load_market_episode_steps
from packages.marl.market_env import AGENT_IDS, AGENT_SPECS, MarketMARLEnvironment


@dataclass(frozen=True, slots=True)
class RLLibTrainingConfig:
    dataset_dir: Path | None = None
    split: str = "train"
    limit: int = 64
    initial_cash_eur: float = 100.0
    iterations: int = 1
    seed: int = 7
    include_supervised_probability: bool = True


class RLLibMarketEnv(MultiAgentEnv):
    """Thin RLlib multi-agent wrapper around ``MarketMARLEnvironment``."""

    def __init__(self, config: Mapping[str, Any] | None = None) -> None:
        super().__init__()
        cfg = dict(config or {})
        dataset_dir = cfg.pop("dataset_dir", None)
        split = str(cfg.pop("split", "train"))
        limit = int(cfg.pop("limit", 64))
        include_supervised_probability = bool(cfg.pop("include_supervised_probability", True))
        initial_cash_eur = cfg.pop("initial_cash_eur", 100.0)

        if dataset_dir is None:
            from apps.cli.run_marl_episode import _demo_steps

            steps = _demo_steps()
        else:
            steps = load_market_episode_steps(Path(str(dataset_dir)), split=split, limit=limit)

        self._env = MarketMARLEnvironment(
            steps,
            initial_cash_eur=_decimal_float(initial_cash_eur),
            include_supervised_probability=include_supervised_probability,
        )
        self._agent_ids = set(AGENT_IDS)
        self.possible_agents = list(AGENT_IDS)
        self._observation_spaces_by_agent: dict[str, spaces.Box] = {
            agent_id: spaces.Box(
                low=-np.inf,
                high=np.inf,
                shape=(len(AGENT_SPECS[agent_id].observation_fields),),
                dtype=np.float32,
            )
            for agent_id in AGENT_IDS
        }
        self._action_spaces_by_agent: dict[str, spaces.Discrete[Any]] = {
            agent_id: spaces.Discrete(len(AGENT_SPECS[agent_id].action_space))
            for agent_id in AGENT_IDS
        }
        self._central_state_space = spaces.Box(
            low=-np.inf,
            high=np.inf,
            shape=(len(MarketMARLEnvironment.central_state_fields),),
            dtype=np.float32,
        )
        self.observation_spaces = self._observation_spaces_by_agent  # type: ignore[assignment]
        self.action_spaces = self._action_spaces_by_agent  # type: ignore[assignment]

    def agent_observation_space(self, agent_id: str) -> spaces.Box:
        return self._observation_spaces_by_agent[agent_id]

    def agent_action_space(self, agent_id: str) -> spaces.Discrete[Any]:
        return self._action_spaces_by_agent[agent_id]

    def central_state_space(self) -> spaces.Box:
        return self._central_state_space

    def central_state(self) -> np.ndarray[Any, np.dtype[np.float32]]:
        return _encode_central_state(self._env.central_state())

    def reset(  # type: ignore[override]
        self,
        *,
        seed: int | None = None,
        options: dict[str, Any] | None = None,
    ) -> tuple[dict[str, np.ndarray[Any, np.dtype[np.float32]]], dict[str, dict[str, Any]]]:
        del seed, options
        observations, infos = self._env.reset()
        return _encode_observations(observations), _with_common_state(infos, self.central_state())

    def step(  # type: ignore[override]
        self,
        action_dict: dict[str, Any],
    ) -> tuple[
        dict[str, np.ndarray[Any, np.dtype[np.float32]]],
        dict[str, float],
        dict[str, bool],
        dict[str, bool],
        dict[str, dict[str, Any]],
    ]:
        actions = {agent_id: int(action_dict.get(agent_id, 0)) for agent_id in AGENT_IDS}
        observations, rewards, terminations, truncations, infos = self._env.step(actions)
        encoded_observations = _encode_observations(observations)
        terminated_all = all(terminations.values()) if terminations else True
        truncated_all = all(truncations.values()) if truncations else False
        return (
            encoded_observations,
            rewards,
            {**terminations, "__all__": terminated_all},
            {**truncations, "__all__": truncated_all},
            _with_common_state(infos, self.central_state()) if encoded_observations else {},
        )


def build_ppo_config(
    *,
    env_name: str,
    training_config: RLLibTrainingConfig,
) -> PPOConfig:
    env = RLLibMarketEnv({})
    policies = {
        agent_id: PolicySpec(
            observation_space=env.agent_observation_space(agent_id),
            action_space=env.agent_action_space(agent_id),
            config={},
        )
        for agent_id in AGENT_IDS
    }
    env_config = _env_config(training_config)
    return (
        PPOConfig()
        .api_stack(
            enable_rl_module_and_learner=False,
            enable_env_runner_and_connector_v2=False,
        )
        .environment(
            env=env_name,
            env_config=env_config,
            disable_env_checking=True,
        )
        .framework("torch")
        .resources(num_gpus=0)
        .env_runners(
            num_env_runners=0,
            rollout_fragment_length=max(1, min(training_config.limit, 32)),
            batch_mode="complete_episodes",
        )
        .training(
            train_batch_size=max(8, training_config.limit),
            minibatch_size=max(4, min(training_config.limit, 16)),
            num_epochs=1,
            lr=0.0003,
        )
        .multi_agent(
            policies=policies,
            policy_mapping_fn=lambda agent_id, *args, **kwargs: str(agent_id),
            count_steps_by="env_steps",
        )
    )


def train_rllib_smoke(training_config: RLLibTrainingConfig) -> dict[str, Any]:
    import ray

    env_name = "csflipper-market-rllib"
    register_env(env_name, lambda config: RLLibMarketEnv(config))
    ray.init(ignore_reinit_error=True, include_dashboard=False, num_cpus=1, log_to_driver=False)
    algorithm = build_ppo_config(env_name=env_name, training_config=training_config).build_algo()
    try:
        result: dict[str, Any] = {}
        for _ in range(training_config.iterations):
            result = algorithm.train()
        evaluation = _evaluate_algorithm(algorithm, _env_config(training_config))
        checkpoint_result = algorithm.save()
        return {
            "algorithm": "PPO multi-agent",
            "ctde_note": "Central state is exposed; centralized critic model is deferred.",
            "iterations": training_config.iterations,
            "episode_reward_mean": result.get("episode_reward_mean"),
            "env_steps_sampled": result.get("num_env_steps_sampled"),
            "evaluation": evaluation,
            "checkpoint": _checkpoint_path(checkpoint_result),
        }
    finally:
        algorithm.stop()
        ray.shutdown()


def _encode_observations(
    observations: Mapping[str, Mapping[str, float]],
) -> dict[str, np.ndarray[Any, np.dtype[np.float32]]]:
    return {
        agent_id: np.asarray(
            [values[field] for field in AGENT_SPECS[agent_id].observation_fields],
            dtype=np.float32,
        )
        for agent_id, values in observations.items()
    }


def _encode_central_state(
    central_state: Mapping[str, float],
) -> np.ndarray[Any, np.dtype[np.float32]]:
    return np.asarray(
        [central_state[field] for field in MarketMARLEnvironment.central_state_fields],
        dtype=np.float32,
    )


def _with_common_state(
    infos: Mapping[str, dict[str, Any]],
    central_state: np.ndarray[Any, np.dtype[np.float32]],
) -> dict[str, dict[str, Any]]:
    return {
        **dict(infos),
        "__common__": {
            "central_state": central_state,
            "central_state_fields": MarketMARLEnvironment.central_state_fields,
        },
    }


def _decimal_float(value: Any) -> Any:
    from decimal import Decimal

    return Decimal(str(value))


def _env_config(training_config: RLLibTrainingConfig) -> dict[str, Any]:
    return {
        "dataset_dir": (
            None if training_config.dataset_dir is None else str(training_config.dataset_dir)
        ),
        "split": training_config.split,
        "limit": training_config.limit,
        "initial_cash_eur": training_config.initial_cash_eur,
        "include_supervised_probability": training_config.include_supervised_probability,
    }


def _evaluate_algorithm(algorithm: Any, env_config: Mapping[str, Any]) -> dict[str, float | int]:
    env = RLLibMarketEnv(env_config)
    observations, _infos = env.reset()
    total_reward = 0.0
    reward_steps = 0
    executed_trades = 0
    while observations:
        actions = {
            agent_id: _action_value(
                algorithm.compute_single_action(
                    observation,
                    policy_id=agent_id,
                    explore=False,
                )
            )
            for agent_id, observation in observations.items()
        }
        observations, rewards, _terminations, _truncations, infos = env.step(actions)
        if rewards:
            total_reward += sum(rewards.values()) / len(rewards)
            reward_steps += 1
        if any(info.get("executed_trade") for info in infos.values()):
            executed_trades += 1
    metrics = env._env.simulator.metrics(as_of=date.today())
    return {
        "mean_step_reward": total_reward / reward_steps if reward_steps else 0.0,
        "executed_trades": executed_trades,
        "positions": len(env._env.simulator.positions),
        "cash_available_eur": float(env._env.simulator.cash_available_eur),
        "realized_profit_eur": float(metrics.realized_profit_eur),
        "drawdown_ratio": float(metrics.drawdown_ratio),
        "capital_blocked_eur": float(metrics.capital_blocked_eur),
        "open_positions": metrics.open_positions,
        "closed_positions": metrics.closed_positions,
    }


def _action_value(action: Any) -> int:
    if isinstance(action, tuple):
        return int(action[0])
    return int(action)


def _checkpoint_path(checkpoint_result: Any) -> str:
    checkpoint = getattr(checkpoint_result, "checkpoint", None)
    if checkpoint is not None:
        return str(checkpoint.path)
    return str(checkpoint_result)

"""Entrenamiento CTDE reproducible sobre episodios históricos de mercado.

Los actores de Scout, Trader y Portfolio solo reciben su observación local. El
modelo evaluador sí recibe el estado central durante el entrenamiento y estima
un valor por rol. Por ello el artefacto resultante puede ejecutar las políticas
en un flujo de recomendaciones sin exponer el estado central a los actores.
"""

from __future__ import annotations

import json
import random
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch import Tensor, nn
from torch.distributions import Categorical

from packages.marl.episodes import MarketEpisodeSource, load_market_episode_source
from packages.marl.market_env import (
    AGENT_IDS,
    AGENT_SPECS,
    AllocationTargetConfig,
    MarketMARLEnvironment,
)
from packages.marl.rewards import CooperativeRewardConfig, HybridRewardConfig


@dataclass(frozen=True, slots=True)
class CTDETrainingConfig:
    dataset_dir: Path
    output_dir: Path
    train_split: str = "train"
    validation_split: str = "validation"
    test_split: str = "test"
    initial_cash_eur: Decimal = Decimal("1000")
    iterations: int = 50
    episodes_per_iteration: int = 8
    episode_days: int = 14
    max_steps_per_episode: int = 2_000
    learning_rate: float = 3e-4
    gamma: float = 0.99
    ppo_clip: float = 0.20
    update_epochs: int = 4
    entropy_weight: float = 0.01
    value_weight: float = 0.50
    seed: int = 7
    include_supervised_probability: bool = True
    reward_config: CooperativeRewardConfig = CooperativeRewardConfig()
    hybrid_reward_config: HybridRewardConfig = HybridRewardConfig()
    allocation_config: AllocationTargetConfig = AllocationTargetConfig()

    def __post_init__(self) -> None:
        if self.iterations <= 0 or self.episodes_per_iteration <= 0:
            raise ValueError("iterations and episodes_per_iteration must be positive")
        if self.episode_days <= 0 or self.max_steps_per_episode <= 0:
            raise ValueError("episode_days and max_steps_per_episode must be positive")
        if not 0 < self.learning_rate:
            raise ValueError("learning_rate must be positive")
        if not 0 < self.gamma <= 1:
            raise ValueError("gamma must be in (0, 1]")


class _Actor(nn.Module):
    def __init__(
        self,
        inputs: int,
        outputs: int,
        *,
        initial_preferred_action: int = 0,
        initial_sell_feature_index: int | None = None,
    ) -> None:
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(inputs, 64),
            nn.Tanh(),
            nn.Linear(64, 64),
            nn.Tanh(),
            nn.Linear(64, outputs),
        )
        self.direct = nn.Linear(inputs, outputs)
        # La exploración comienza con una ligera preferencia por la acción
        # operativa. Así se obtienen cierres y recompensas observables desde
        # los primeros episodios; los pesos aprendidos pueden revertirla.
        with torch.no_grad():
            output = self.network[-1]
            if isinstance(output, nn.Linear):
                nn.init.zeros_(output.weight)
                nn.init.zeros_(output.bias)
                nn.init.zeros_(self.direct.weight)
                nn.init.zeros_(self.direct.bias)
                self.direct.bias[initial_preferred_action] = 0.50
                if initial_sell_feature_index is not None and outputs > 2:
                    self.direct.bias[2] = -0.20
                    self.direct.weight[2, initial_sell_feature_index] = 1.0

    def forward(self, observation: Tensor) -> Tensor:
        return self.network(observation) + self.direct(observation)


class _CentralEvaluator(nn.Module):
    def __init__(self, inputs: int, roles: int) -> None:
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(inputs, 96),
            nn.Tanh(),
            nn.Linear(96, 64),
            nn.Tanh(),
            nn.Linear(64, roles),
        )

    def forward(self, state: Tensor) -> Tensor:
        return self.network(state)


@dataclass(slots=True)
class _Rollout:
    observations: dict[str, list[np.ndarray[Any, Any]]]
    states: list[np.ndarray[Any, Any]]
    actions: dict[str, list[int]]
    action_masks: dict[str, list[np.ndarray[Any, Any]]]
    log_probabilities: dict[str, list[float]]
    rewards: dict[str, list[float]]
    mean_common_reward: float
    final_equity_return: float
    closed_operations: int


class CTDEPolicy:
    """Políticas de ejecución descentralizada cargables desde un checkpoint."""

    def __init__(self, actors: dict[str, _Actor]) -> None:
        self._actors = actors
        for actor in self._actors.values():
            actor.eval()

    def select_actions(
        self,
        observations: dict[str, dict[str, float]],
        *,
        action_masks: dict[str, tuple[int, ...]] | None = None,
    ) -> dict[str, int]:
        with torch.no_grad():
            return {
                agent_id: int(
                    torch.argmax(
                        _masked_logits(
                            self._actors[agent_id](
                                _observation_tensor(agent_id, observations[agent_id])
                            ),
                            None if action_masks is None else action_masks[agent_id],
                        )
                    ).item()
                )
                for agent_id in AGENT_IDS
            }


def train_ctde(config: CTDETrainingConfig) -> dict[str, Any]:
    """Entrena, valida y guarda políticas CTDE con datos históricos temporales."""

    _seed_everything(config.seed)
    config.output_dir.mkdir(parents=True, exist_ok=True)
    train_source = load_market_episode_source(config.dataset_dir, split=config.train_split)
    validation_source = load_market_episode_source(config.dataset_dir, split=config.validation_split)
    test_source = load_market_episode_source(config.dataset_dir, split=config.test_split)
    actors, evaluator = _models()
    optimizer = torch.optim.Adam(
        [parameter for model in (*actors.values(), evaluator) for parameter in model.parameters()],
        lr=config.learning_rate,
    )
    train_rng = random.Random(config.seed)
    validation_rng = random.Random(config.seed + 1)
    baseline_validation = _evaluate_source(
        validation_source,
        actors,
        config=config,
        rng=validation_rng,
        episodes=max(1, min(4, config.episodes_per_iteration)),
    )
    best_validation = float(baseline_validation["equity_return"])
    history: list[dict[str, float | int]] = []
    checkpoint_path = config.output_dir / "best_checkpoint.pt"
    _save_checkpoint(
        checkpoint_path,
        actors=actors,
        evaluator=evaluator,
        config=config,
        iteration=0,
        validation=baseline_validation,
    )

    for iteration in range(1, config.iterations + 1):
        rollouts = [
            _sample_rollout(train_source, actors, config=config, rng=train_rng, explore=True)
            for _ in range(config.episodes_per_iteration)
        ]
        losses = _update_models(actors, evaluator, optimizer, rollouts, config=config)
        validation = _evaluate_source(
            validation_source,
            actors,
            config=config,
            rng=validation_rng,
            episodes=max(1, min(4, config.episodes_per_iteration)),
        )
        training = _rollout_metrics(rollouts)
        row: dict[str, float | int] = {
            "iteration": iteration,
            **training,
            **{f"validation_{key}": value for key, value in validation.items()},
            **losses,
        }
        history.append(row)
        if validation["equity_return"] > best_validation:
            best_validation = validation["equity_return"]
            _save_checkpoint(
                checkpoint_path,
                actors=actors,
                evaluator=evaluator,
                config=config,
                iteration=iteration,
                validation=validation,
            )

    _load_checkpoint_weights(checkpoint_path, actors, evaluator)
    test = _evaluate_source(
        test_source,
        actors,
        config=config,
        rng=random.Random(config.seed + 2),
        episodes=max(1, min(8, config.episodes_per_iteration)),
    )
    report = {
        "algorithm": "CTDE actor-critic multiagente",
        "actors": list(AGENT_IDS),
        "central_evaluator": "solo entrenamiento",
        "dataset_dir": str(config.dataset_dir),
        "splits": {
            "train": config.train_split,
            "validation": config.validation_split,
            "test": config.test_split,
        },
        "checkpoint": str(checkpoint_path),
        "best_validation_equity_return": best_validation,
        "test": test,
        "history": history,
    }
    report_path = config.output_dir / "training_report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    _write_metadata(config.output_dir / "metadata.json", config=config, report=report)
    return report


def load_ctde_policy(checkpoint_path: Path | str) -> CTDEPolicy:
    actors, evaluator = _models()
    _load_checkpoint_weights(Path(checkpoint_path), actors, evaluator)
    return CTDEPolicy(actors)


def _models() -> tuple[dict[str, _Actor], _CentralEvaluator]:
    actors = {
        agent_id: _Actor(
            len(AGENT_SPECS[agent_id].observation_fields),
            len(AGENT_SPECS[agent_id].action_space),
            initial_preferred_action=1,
            initial_sell_feature_index=(
                AGENT_SPECS[agent_id].observation_fields.index("matching_sellable_positions")
                if agent_id == "trader"
                else None
            ),
        )
        for agent_id in AGENT_IDS
    }
    evaluator = _CentralEvaluator(
        len(MarketMARLEnvironment.central_state_fields),
        len(AGENT_IDS),
    )
    return actors, evaluator


def _sample_rollout(
    source: MarketEpisodeSource,
    actors: dict[str, _Actor],
    *,
    config: CTDETrainingConfig,
    rng: random.Random,
    explore: bool,
) -> _Rollout:
    steps = source.sample_window(
        days=config.episode_days,
        rng=rng,
        max_steps=config.max_steps_per_episode,
    )
    env = MarketMARLEnvironment(
        steps,
        initial_cash_eur=config.initial_cash_eur,
        reward_config=config.reward_config,
        hybrid_reward_config=config.hybrid_reward_config,
        allocation_config=config.allocation_config,
        include_supervised_probability=config.include_supervised_probability,
    )
    observations, _infos = env.reset()
    rollout = _empty_rollout()
    common_rewards: list[float] = []
    while env.agents:
        central_state = _central_state_tensor(env.central_state())
        action_masks = env.action_masks()
        actions: dict[str, int] = {}
        for agent_id in AGENT_IDS:
            observation = _observation_tensor(agent_id, observations[agent_id])
            mask = action_masks[agent_id]
            logits = _masked_logits(actors[agent_id](observation), mask)
            distribution = Categorical(logits=logits)
            action = distribution.sample() if explore else torch.argmax(logits)
            rollout.observations[agent_id].append(observation.detach().numpy())
            rollout.actions[agent_id].append(int(action.item()))
            rollout.action_masks[agent_id].append(np.asarray(mask, dtype=np.bool_))
            rollout.log_probabilities[agent_id].append(float(distribution.log_prob(action).item()))
            actions[agent_id] = int(action.item())
        rollout.states.append(central_state.detach().numpy())
        observations, rewards, _terminations, _truncations, infos = env.step(actions)
        common_rewards.append(float(infos["scout"]["reward_breakdown"]["total"]))
        for agent_id in AGENT_IDS:
            rollout.rewards[agent_id].append(float(rewards[agent_id]))
        if infos["trader"].get("executed_sale"):
            rollout.closed_operations += 1

    metrics = env.simulator.metrics(as_of=steps[-1].observed_day)
    rollout.mean_common_reward = float(np.mean(common_rewards)) if common_rewards else 0.0
    rollout.final_equity_return = float(
        (metrics.equity_eur - config.initial_cash_eur) / config.initial_cash_eur
    )
    return rollout


def _empty_rollout() -> _Rollout:
    return _Rollout(
        observations={agent_id: [] for agent_id in AGENT_IDS},
        states=[],
        actions={agent_id: [] for agent_id in AGENT_IDS},
        action_masks={agent_id: [] for agent_id in AGENT_IDS},
        log_probabilities={agent_id: [] for agent_id in AGENT_IDS},
        rewards={agent_id: [] for agent_id in AGENT_IDS},
        mean_common_reward=0.0,
        final_equity_return=0.0,
        closed_operations=0,
    )


def _update_models(
    actors: dict[str, _Actor],
    evaluator: _CentralEvaluator,
    optimizer: torch.optim.Optimizer,
    rollouts: list[_Rollout],
    *,
    config: CTDETrainingConfig,
) -> dict[str, float]:
    states = torch.as_tensor(np.concatenate([rollout.states for rollout in rollouts]), dtype=torch.float32)
    returns = {
        agent_id: torch.as_tensor(
            np.concatenate(
                [_discounted_returns(rollout.rewards[agent_id], config.gamma) for rollout in rollouts]
            ),
            dtype=torch.float32,
        )
        for agent_id in AGENT_IDS
    }
    observations = {
        agent_id: torch.as_tensor(
            np.concatenate([rollout.observations[agent_id] for rollout in rollouts]),
            dtype=torch.float32,
        )
        for agent_id in AGENT_IDS
    }
    actions = {
        agent_id: torch.as_tensor(
            np.concatenate([rollout.actions[agent_id] for rollout in rollouts]), dtype=torch.int64
        )
        for agent_id in AGENT_IDS
    }
    action_masks = {
        agent_id: torch.as_tensor(
            np.concatenate([rollout.action_masks[agent_id] for rollout in rollouts]),
            dtype=torch.bool,
        )
        for agent_id in AGENT_IDS
    }
    old_log_probabilities = {
        agent_id: torch.as_tensor(
            np.concatenate([rollout.log_probabilities[agent_id] for rollout in rollouts]),
            dtype=torch.float32,
        )
        for agent_id in AGENT_IDS
    }
    with torch.no_grad():
        baseline = evaluator(states)
    advantages = {
        agent_id: _normalise(returns[agent_id] - baseline[:, index])
        for index, agent_id in enumerate(AGENT_IDS)
    }
    last_actor_loss = 0.0
    last_value_loss = 0.0
    for _ in range(config.update_epochs):
        values = evaluator(states)
        actor_losses: list[Tensor] = []
        entropies: list[Tensor] = []
        for agent_id in AGENT_IDS:
            distribution = Categorical(
                logits=_masked_logits(actors[agent_id](observations[agent_id]), action_masks[agent_id])
            )
            log_probability = distribution.log_prob(actions[agent_id])
            ratio = torch.exp(log_probability - old_log_probabilities[agent_id])
            unclipped = ratio * advantages[agent_id]
            clipped = torch.clamp(
                ratio,
                1 - config.ppo_clip,
                1 + config.ppo_clip,
            ) * advantages[agent_id]
            actor_losses.append(-torch.minimum(unclipped, clipped).mean())
            entropies.append(distribution.entropy().mean())
        value_loss = sum(
            nn.functional.mse_loss(values[:, index], returns[agent_id])
            for index, agent_id in enumerate(AGENT_IDS)
        ) / len(AGENT_IDS)
        actor_loss = sum(actor_losses) / len(actor_losses)
        entropy = sum(entropies) / len(entropies)
        loss = actor_loss + config.value_weight * value_loss - config.entropy_weight * entropy
        optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(
            [parameter for model in (*actors.values(), evaluator) for parameter in model.parameters()],
            max_norm=1.0,
        )
        optimizer.step()
        last_actor_loss = float(actor_loss.item())
        last_value_loss = float(value_loss.item())
    return {"actor_loss": last_actor_loss, "value_loss": last_value_loss}


def _evaluate_source(
    source: MarketEpisodeSource,
    actors: dict[str, _Actor],
    *,
    config: CTDETrainingConfig,
    rng: random.Random,
    episodes: int,
) -> dict[str, float | int]:
    for actor in actors.values():
        actor.eval()
    with torch.no_grad():
        rollouts = [
            _sample_rollout(source, actors, config=config, rng=rng, explore=False)
            for _ in range(episodes)
        ]
    for actor in actors.values():
        actor.train()
    return _rollout_metrics(rollouts)


def _rollout_metrics(rollouts: list[_Rollout]) -> dict[str, float | int]:
    return {
        "episodes": len(rollouts),
        "equity_return": float(np.mean([rollout.final_equity_return for rollout in rollouts])),
        "mean_common_reward": float(np.mean([rollout.mean_common_reward for rollout in rollouts])),
        "closed_operations": int(sum(rollout.closed_operations for rollout in rollouts)),
    }


def _discounted_returns(rewards: list[float], gamma: float) -> np.ndarray[Any, Any]:
    result = np.zeros(len(rewards), dtype=np.float32)
    accumulated = 0.0
    for index in range(len(rewards) - 1, -1, -1):
        accumulated = rewards[index] + gamma * accumulated
        result[index] = accumulated
    return result


def _normalise(values: Tensor) -> Tensor:
    return (values - values.mean()) / (values.std(unbiased=False) + 1e-8)


def _observation_tensor(agent_id: str, observation: dict[str, float]) -> Tensor:
    return torch.as_tensor(
        [observation[field] for field in AGENT_SPECS[agent_id].observation_fields],
        dtype=torch.float32,
    )


def _central_state_tensor(state: dict[str, float]) -> Tensor:
    return torch.as_tensor(
        [state[field] for field in MarketMARLEnvironment.central_state_fields],
        dtype=torch.float32,
    )


def _masked_logits(logits: Tensor, action_mask: Tensor | tuple[int, ...] | None) -> Tensor:
    """Elimina acciones imposibles antes de muestrear o actualizar una política."""

    if action_mask is None:
        return logits
    mask = torch.as_tensor(action_mask, dtype=torch.bool, device=logits.device)
    return logits.masked_fill(~mask, torch.finfo(logits.dtype).min)


def _save_checkpoint(
    path: Path,
    *,
    actors: dict[str, _Actor],
    evaluator: _CentralEvaluator,
    config: CTDETrainingConfig,
    iteration: int,
    validation: dict[str, float | int],
) -> None:
    torch.save(
        {
            "actors": {agent_id: actor.state_dict() for agent_id, actor in actors.items()},
            "evaluator": evaluator.state_dict(),
            "iteration": iteration,
            "validation": validation,
            "observation_fields": {
                agent_id: list(AGENT_SPECS[agent_id].observation_fields) for agent_id in AGENT_IDS
            },
            "central_state_fields": list(MarketMARLEnvironment.central_state_fields),
            "reward_config": _reward_config_dict(config.reward_config),
            "hybrid_reward_config": {"shared_weight": str(config.hybrid_reward_config.shared_weight)},
            "allocation_config": {
                "target_fraction": str(config.allocation_config.target_fraction),
                "tolerance": str(config.allocation_config.tolerance),
            },
        },
        path,
    )


def _load_checkpoint_weights(
    path: Path,
    actors: dict[str, _Actor],
    evaluator: _CentralEvaluator,
) -> None:
    checkpoint = torch.load(path, map_location="cpu", weights_only=True)
    for agent_id, actor in actors.items():
        actor.load_state_dict(checkpoint["actors"][agent_id])
    evaluator.load_state_dict(checkpoint["evaluator"])


def _write_metadata(path: Path, *, config: CTDETrainingConfig, report: dict[str, Any]) -> None:
    payload = {
        "schema_version": "csflipper_ctde_marl.v1",
        "created_at": datetime.now(tz=UTC).isoformat(),
        "training": {
            **asdict(config),
            "dataset_dir": str(config.dataset_dir),
            "output_dir": str(config.output_dir),
            "initial_cash_eur": str(config.initial_cash_eur),
            "reward_config": _reward_config_dict(config.reward_config),
            "hybrid_reward_config": {"shared_weight": str(config.hybrid_reward_config.shared_weight)},
        },
        "best_validation_equity_return": report["best_validation_equity_return"],
        "test": report["test"],
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def _reward_config_dict(config: CooperativeRewardConfig) -> dict[str, str]:
    return {
        "roi_weight": str(config.roi_weight),
        "extra_hold_day_penalty": str(config.extra_hold_day_penalty),
        "constraint_violation_penalty": str(config.constraint_violation_penalty),
    }


def _seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)

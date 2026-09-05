"""PPO centralizado de referencia para comparar la arquitectura MARL.

La política única observa el estado global y elige una de las acciones conjuntas
válidas. No comparte parámetros con los tres actores MARL y se entrena solo con
entrenamiento y validación.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch import Tensor, nn
from torch.distributions import Categorical

from packages.marl.ctde_training import CTDETrainingConfig
from packages.marl.episodes import MarketEpisodeSource, load_market_episode_source
from packages.marl.market_env import AGENT_SPECS, MarketMARLEnvironment

JOINT_ACTIONS: tuple[dict[str, int], ...] = tuple(
    {
        "scout": scout_action,
        "trader": trader_action,
        "portfolio": portfolio_action,
    }
    for scout_action in AGENT_SPECS["scout"].action_space
    for trader_action in AGENT_SPECS["trader"].action_space
    for portfolio_action in AGENT_SPECS["portfolio"].action_space
)


class _SingleActor(nn.Module):
    def __init__(self, inputs: int, outputs: int) -> None:
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(inputs, 96),
            nn.Tanh(),
            nn.Linear(96, 64),
            nn.Tanh(),
            nn.Linear(64, outputs),
        )
        with torch.no_grad():
            output = self.network[-1]
            if isinstance(output, nn.Linear):
                nn.init.zeros_(output.weight)
                nn.init.zeros_(output.bias)

    def forward(self, state: Tensor) -> Tensor:
        return self.network(state)  # type: ignore[no-any-return]


class _SingleCritic(nn.Module):
    def __init__(self, inputs: int) -> None:
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(inputs, 96),
            nn.Tanh(),
            nn.Linear(96, 64),
            nn.Tanh(),
            nn.Linear(64, 1),
        )

    def forward(self, state: Tensor) -> Tensor:
        return self.network(state).squeeze(-1)  # type: ignore[no-any-return]


class SingleAgentPolicy:
    """Política centralizada que devuelve la acción conjunta del simulador."""

    def __init__(self, actor: _SingleActor) -> None:
        self._actor = actor.eval()

    def select_actions(
        self,
        state: dict[str, float],
        action_masks: dict[str, tuple[int, ...]],
    ) -> dict[str, int]:
        with torch.no_grad():
            logits = _masked_logits(self._actor(_state_tensor(state)), _joint_mask(action_masks))
            return dict(JOINT_ACTIONS[int(torch.argmax(logits).item())])


@dataclass(slots=True)
class _Rollout:
    states: list[np.ndarray[Any, Any]]
    actions: list[int]
    masks: list[np.ndarray[Any, Any]]
    log_probabilities: list[float]
    rewards: list[float]
    final_equity_return: float


def train_single_agent(config: CTDETrainingConfig) -> dict[str, Any]:
    """Entrena una referencia PPO centralizada sin acceder a la prueba."""

    _seed(config.seed)
    config.output_dir.mkdir(parents=True, exist_ok=True)
    item_ids = None if config.asset_ids is None else frozenset(config.asset_ids)
    train_source = load_market_episode_source(
        config.dataset_dir, split=config.train_split, item_ids=item_ids
    )
    validation_source = load_market_episode_source(
        config.dataset_dir, split=config.validation_split, item_ids=item_ids
    )
    actor = _SingleActor(len(MarketMARLEnvironment.central_state_fields), len(JOINT_ACTIONS))
    critic = _SingleCritic(len(MarketMARLEnvironment.central_state_fields))
    optimizer = torch.optim.Adam(
        (*actor.parameters(), *critic.parameters()), lr=config.learning_rate
    )
    checkpoint_path = config.output_dir / "best_checkpoint.pt"
    initial_validation = _evaluate(
        validation_source,
        actor,
        config=config,
        rng=random.Random(config.validation_seed),
        episodes=min(4, config.episodes_per_iteration),
    )
    best_validation = initial_validation
    _save_checkpoint(checkpoint_path, actor, critic, config, 0, initial_validation)
    patience = 0
    history: list[dict[str, float | int]] = []
    train_rng = random.Random(config.seed)
    stopped_early = False

    for iteration in range(1, config.iterations + 1):
        rollouts = [
            _rollout(train_source, actor, config=config, rng=train_rng, explore=True)
            for _ in range(config.episodes_per_iteration)
        ]
        losses = _update(actor, critic, optimizer, rollouts, config)
        validation = _evaluate(
            validation_source,
            actor,
            config=config,
            rng=random.Random(config.validation_seed),
            episodes=min(4, config.episodes_per_iteration),
        )
        history.append(
            {
                "iteration": iteration,
                "mean_common_reward": float(np.mean([np.mean(item.rewards) for item in rollouts])),
                "validation_equity_return": validation,
                **losses,
            }
        )
        if validation > best_validation:
            best_validation = validation
            patience = 0
            _save_checkpoint(checkpoint_path, actor, critic, config, iteration, validation)
        else:
            patience += 1
        if (
            config.early_stopping_patience is not None
            and patience >= config.early_stopping_patience
        ):
            stopped_early = True
            break

    report = {
        "algorithm": "PPO centralizado de agente único",
        "dataset_dir": str(config.dataset_dir),
        "checkpoint": str(checkpoint_path),
        "best_validation_equity_return": best_validation,
        "executed_iterations": len(history),
        "stopped_early": stopped_early,
        "scenario": {"name": config.scenario_name, "asset_ids": list(config.asset_ids or ())},
        "history": history,
        "test_used": False,
    }
    (config.output_dir / "training_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return report


def load_single_agent_policy(checkpoint_path: Path | str) -> SingleAgentPolicy:
    actor = _SingleActor(len(MarketMARLEnvironment.central_state_fields), len(JOINT_ACTIONS))
    checkpoint = torch.load(Path(checkpoint_path), map_location="cpu", weights_only=True)
    actor.load_state_dict(checkpoint["actor"])
    return SingleAgentPolicy(actor)


def _rollout(
    source: MarketEpisodeSource,
    actor: _SingleActor,
    *,
    config: CTDETrainingConfig,
    rng: random.Random,
    explore: bool,
) -> _Rollout:
    steps = source.sample_window(
        days=config.episode_days, rng=rng, max_steps=config.max_steps_per_episode
    )
    env = MarketMARLEnvironment(
        steps,
        initial_cash_eur=config.initial_cash_eur,
        risk_config=config.risk_config,
        reward_config=config.reward_config,
        hybrid_reward_config=config.hybrid_reward_config,
        allocation_config=config.allocation_config,
        include_supervised_probability=config.include_supervised_probability,
    )
    env.reset()
    rollout = _Rollout([], [], [], [], [], 0.0)
    while env.agents:
        state = _state_tensor(env.central_state())
        mask = _joint_mask(env.action_masks())
        logits = _masked_logits(actor(state), mask)
        distribution = Categorical(logits=logits)
        action = distribution.sample() if explore else torch.argmax(logits)  # type: ignore[no-untyped-call]
        _observations, _rewards, _terminations, _truncations, infos = env.step(
            JOINT_ACTIONS[int(action.item())]
        )
        rollout.states.append(state.detach().numpy())
        rollout.actions.append(int(action.item()))
        rollout.masks.append(mask.detach().numpy())
        rollout.log_probabilities.append(float(distribution.log_prob(action).item()))  # type: ignore[no-untyped-call]
        rollout.rewards.append(float(infos["scout"]["reward_breakdown"]["total"]))
    metrics = env.simulator.metrics(as_of=steps[-1].observed_day)
    rollout.final_equity_return = float(
        (metrics.equity_eur - config.initial_cash_eur) / config.initial_cash_eur
    )
    return rollout


def _evaluate(
    source: MarketEpisodeSource,
    actor: _SingleActor,
    *,
    config: CTDETrainingConfig,
    rng: random.Random,
    episodes: int,
) -> float:
    actor.eval()
    with torch.no_grad():
        value = float(
            np.mean(
                [
                    _rollout(
                        source, actor, config=config, rng=rng, explore=False
                    ).final_equity_return
                    for _ in range(max(1, episodes))
                ]
            )
        )
    actor.train()
    return value


def _update(
    actor: _SingleActor,
    critic: _SingleCritic,
    optimizer: torch.optim.Optimizer,
    rollouts: list[_Rollout],
    config: CTDETrainingConfig,
) -> dict[str, float]:
    states = torch.as_tensor(
        np.concatenate([item.states for item in rollouts]), dtype=torch.float32
    )
    actions = torch.as_tensor(
        np.concatenate([item.actions for item in rollouts]), dtype=torch.int64
    )
    masks = torch.as_tensor(np.concatenate([item.masks for item in rollouts]), dtype=torch.bool)
    old_log_probabilities = torch.as_tensor(
        np.concatenate([item.log_probabilities for item in rollouts]), dtype=torch.float32
    )
    returns = torch.as_tensor(
        np.concatenate([_discount(item.rewards, config.gamma) for item in rollouts]),
        dtype=torch.float32,
    )
    with torch.no_grad():
        advantages = _normalise(returns - critic(states))
    actor_losses: list[float] = []
    value_losses: list[float] = []
    for _ in range(config.update_epochs):
        distribution = Categorical(logits=_masked_logits(actor(states), masks))
        log_probability = distribution.log_prob(actions)  # type: ignore[no-untyped-call]
        ratio = torch.exp(log_probability - old_log_probabilities)
        actor_loss = -torch.minimum(
            ratio * advantages,
            torch.clamp(ratio, 1 - config.ppo_clip, 1 + config.ppo_clip) * advantages,
        ).mean()
        value_loss = nn.functional.mse_loss(critic(states), returns)
        entropy = distribution.entropy()  # type: ignore[no-untyped-call]
        loss = (
            actor_loss
            + config.value_weight * value_loss
            - config.entropy_weight * entropy.mean()
        )
        optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_((*actor.parameters(), *critic.parameters()), max_norm=1.0)
        optimizer.step()
        actor_losses.append(float(actor_loss.item()))
        value_losses.append(float(value_loss.item()))
    return {"actor_loss": float(np.mean(actor_losses)), "value_loss": float(np.mean(value_losses))}


def _state_tensor(state: dict[str, float]) -> Tensor:
    return torch.as_tensor(
        [state[field] for field in MarketMARLEnvironment.central_state_fields], dtype=torch.float32
    )


def _joint_mask(action_masks: dict[str, tuple[int, ...]]) -> Tensor:
    return torch.as_tensor(
        [
            bool(action_masks["scout"][action["scout"]])
            and bool(action_masks["trader"][action["trader"]])
            and bool(action_masks["portfolio"][action["portfolio"]])
            for action in JOINT_ACTIONS
        ],
        dtype=torch.bool,
    )


def _masked_logits(logits: Tensor, mask: Tensor) -> Tensor:
    return logits.masked_fill(~mask, torch.finfo(logits.dtype).min)


def _discount(rewards: list[float], gamma: float) -> np.ndarray[Any, Any]:
    result = np.zeros(len(rewards), dtype=np.float32)
    running = 0.0
    for index in range(len(rewards) - 1, -1, -1):
        running = rewards[index] + gamma * running
        result[index] = running
    return result


def _normalise(values: Tensor) -> Tensor:
    return (values - values.mean()) / (values.std(unbiased=False) + 1e-8)


def _save_checkpoint(
    path: Path,
    actor: _SingleActor,
    critic: _SingleCritic,
    config: CTDETrainingConfig,
    iteration: int,
    validation: float,
) -> None:
    torch.save(
        {
            "actor": actor.state_dict(),
            "critic": critic.state_dict(),
            "iteration": iteration,
            "validation": validation,
            "scenario": {"asset_ids": list(config.asset_ids or ())},
        },
        path,
    )


def _seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)

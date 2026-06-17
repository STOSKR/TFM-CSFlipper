"""PettingZoo ParallelEnv wrapper for the CSFlipper market MARL core."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Any

import numpy as np
from gymnasium import spaces
from pettingzoo import ParallelEnv  # type: ignore[import-untyped]

from packages.marl.market_env import (
    AGENT_IDS,
    AGENT_SPECS,
    MarketEpisodeStep,
    MarketMARLEnvironment,
)


class PettingZooMarketEnv(ParallelEnv):  # type: ignore[misc]
    """PettingZoo parallel wrapper with fixed vector observations per agent."""

    metadata = {"name": "csflipper_market_v0", "render_modes": []}

    def __init__(
        self,
        episode_steps: Sequence[MarketEpisodeStep],
        *,
        initial_cash_eur: Decimal = Decimal("1000"),
        include_supervised_probability: bool = True,
    ) -> None:
        self.possible_agents = list(AGENT_IDS)
        self.agents = list(AGENT_IDS)
        self._env = MarketMARLEnvironment(
            episode_steps,
            initial_cash_eur=initial_cash_eur,
            include_supervised_probability=include_supervised_probability,
        )
        self._observation_spaces = {
            agent_id: spaces.Box(
                low=-np.inf,
                high=np.inf,
                shape=(len(AGENT_SPECS[agent_id].observation_fields),),
                dtype=np.float32,
            )
            for agent_id in AGENT_IDS
        }
        self._action_spaces: dict[str, spaces.Discrete[Any]] = {
            agent_id: spaces.Discrete(2) for agent_id in AGENT_IDS
        }

    def observation_space(self, agent: str) -> spaces.Box:
        return self._observation_spaces[agent]

    def action_space(self, agent: str) -> spaces.Discrete[Any]:
        return self._action_spaces[agent]

    def reset(
        self,
        seed: int | None = None,
        options: dict[str, Any] | None = None,
    ) -> tuple[dict[str, np.ndarray[Any, np.dtype[np.float32]]], dict[str, dict[str, Any]]]:
        del seed, options
        self.agents = list(AGENT_IDS)
        observations, infos = self._env.reset()
        return _encode_observations(observations), infos

    def step(
        self,
        actions: dict[str, Any],
    ) -> tuple[
        dict[str, np.ndarray[Any, np.dtype[np.float32]]],
        dict[str, float],
        dict[str, bool],
        dict[str, bool],
        dict[str, dict[str, Any]],
    ]:
        observations, rewards, terminations, truncations, infos = self._env.step(
            {agent_id: int(actions.get(agent_id, 0)) for agent_id in AGENT_IDS}
        )
        self.agents = list(self._env.agents)
        return _encode_observations(observations), rewards, terminations, truncations, infos


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

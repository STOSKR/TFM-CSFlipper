"""Small RLlib registration helpers for the market MARL environment."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from decimal import Decimal
from pathlib import Path
from typing import Any

from packages.marl.episodes import load_market_episode_steps
from packages.marl.market_env import MarketEpisodeStep, MarketMARLEnvironment

EnvConfig = Mapping[str, Any] | None
EnvCreator = Callable[[EnvConfig], MarketMARLEnvironment]
RegisterEnv = Callable[[str, EnvCreator], None]


def market_env_creator(
    default_steps: Sequence[MarketEpisodeStep] | None = None,
    **default_kwargs: Any,
) -> EnvCreator:
    steps = tuple(default_steps) if default_steps is not None else None

    def create(config: EnvConfig = None) -> MarketMARLEnvironment:
        cfg = dict(config or {})
        episode_steps = cfg.pop("episode_steps", steps)
        dataset_path = cfg.pop("dataset_path", None)
        split = str(cfg.pop("split", "train"))
        limit = cfg.pop("limit", None)

        if episode_steps is None:
            if dataset_path is None:
                raise ValueError("episode_steps or dataset_path is required")
            episode_steps = load_market_episode_steps(
                Path(str(dataset_path)),
                split=split,
                limit=None if limit is None else int(limit),
            )

        kwargs = {**default_kwargs, **cfg}
        if "initial_cash_eur" in kwargs:
            kwargs["initial_cash_eur"] = Decimal(str(kwargs["initial_cash_eur"]))
        return MarketMARLEnvironment(tuple(episode_steps), **kwargs)

    return create


def register_market_env(
    name: str,
    register_env: RegisterEnv,
    default_steps: Sequence[MarketEpisodeStep] | None = None,
    **default_kwargs: Any,
) -> None:
    register_env(name, market_env_creator(default_steps, **default_kwargs))

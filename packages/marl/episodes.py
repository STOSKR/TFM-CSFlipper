"""Load MARL market episodes from versioned parquet datasets."""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pandas as pd  # type: ignore[import-untyped]

from packages.marl.market_env import MarketEpisodeStep


@dataclass(frozen=True, slots=True)
class MarketEpisodeSource:
    """Colección temporal de pasos desde la que se extraen episodios contiguos."""

    steps: tuple[MarketEpisodeStep, ...]

    def __post_init__(self) -> None:
        if not self.steps:
            raise ValueError("steps cannot be empty")

    @property
    def days(self) -> tuple[date, ...]:
        return tuple(sorted({step.observed_day for step in self.steps}))

    def sample_window(
        self,
        *,
        days: int,
        rng: random.Random,
        max_steps: int | None = None,
    ) -> tuple[MarketEpisodeStep, ...]:
        """Selecciona una ventana de días consecutivos sin reordenar el tiempo."""

        if days <= 0:
            raise ValueError("days must be positive")
        available_days = self.days
        latest_full_start = available_days[-1] - timedelta(days=days - 1)
        eligible_indices = [
            index
            for index, observed_day in enumerate(available_days)
            if observed_day <= latest_full_start
        ]
        start_index = rng.choice(eligible_indices or list(range(len(available_days))))
        start_day = available_days[start_index]
        end_day = start_day + timedelta(days=days - 1)
        window = tuple(step for step in self.steps if start_day <= step.observed_day <= end_day)
        if not window:
            window = (self.steps[start_index % len(self.steps)],)
        if max_steps is not None:
            if max_steps <= 0:
                raise ValueError("max_steps must be positive when supplied")
            window = window[:max_steps]
        return window


def select_price_stratified_item_ids(
    path: Path | str,
    *,
    asset_count: int | None,
    train_split: str = "train",
    validation_split: str = "validation",
    maximum_item_price_eur: float | None = None,
) -> tuple[str, ...] | None:
    """Selecciona activos de forma determinista sin consultar la prueba.

    La selección usa únicamente los cortes de entrenamiento y validación. Cada
    activo se ordena por su precio mediano observado en entrenamiento y se
    escogen puntos repartidos por todo ese rango, para no construir escenarios
    formados solo por activos baratos o caros.
    """

    if asset_count is None:
        return None
    if asset_count <= 0:
        raise ValueError("asset_count must be positive when supplied")
    train_steps = load_market_episode_steps(path, split=train_split)
    validation_steps = load_market_episode_steps(path, split=validation_split)
    validation_ids = {step.item_id for step in validation_steps}
    prices_by_item: dict[str, list[float]] = {}
    for step in train_steps:
        if step.item_id in validation_ids:
            prices_by_item.setdefault(step.item_id, []).append(float(step.buy_price_eur))
    ranked = sorted(
        (
            (float(pd.Series(prices).median()), item_id)
            for item_id, prices in prices_by_item.items()
            if (
                maximum_item_price_eur is None
                or float(pd.Series(prices).median()) <= maximum_item_price_eur
            )
        ),
        key=lambda pair: (pair[0], pair[1]),
    )
    if len(ranked) < asset_count:
        raise ValueError(
            f"only {len(ranked)} assets satisfy the scenario but {asset_count} were requested"
        )
    if asset_count == len(ranked):
        return tuple(item_id for _price, item_id in ranked)
    indices = [round(index * (len(ranked) - 1) / (asset_count - 1)) for index in range(asset_count)]
    if asset_count == 1:
        indices = [len(ranked) // 2]
    return tuple(ranked[index][1] for index in indices)


def load_market_episode_steps(
    path: Path | str,
    *,
    split: str = "train",
    limit: int | None = None,
    item_ids: frozenset[str] | None = None,
) -> tuple[MarketEpisodeStep, ...]:
    source_path = Path(path)
    parquet_path = _parquet_path(source_path, split=split)
    route_defaults = _route_defaults(source_path)
    frame = pd.read_parquet(parquet_path)
    if item_ids is not None:
        frame = frame[frame["item_id"].isin(item_ids)]
    if limit is not None:
        frame = frame.head(limit)
    rows = (
        {**route_defaults, **dict(row)}
        for row in frame.sort_values(["observed_day", "item_id"]).to_dict(orient="records")
    )
    return tuple(MarketEpisodeStep.from_mapping(row) for row in rows)


def load_market_episode_source(
    path: Path | str,
    *,
    split: str = "train",
    item_ids: frozenset[str] | None = None,
) -> MarketEpisodeSource:
    """Carga un corte temporal completo para muestrear episodios de entrenamiento."""

    return MarketEpisodeSource(load_market_episode_steps(path, split=split, item_ids=item_ids))


def _parquet_path(path: Path, *, split: str) -> Path:
    if path.is_file():
        return path
    candidate = path / f"{split}.parquet"
    if candidate.exists():
        return candidate
    raise FileNotFoundError(f"no parquet file found for split {split!r} in {path}")


def _route_defaults(path: Path) -> dict[str, str]:
    if path.is_file():
        return {}
    metadata_path = path / "metadata.json"
    if not metadata_path.exists():
        return {}
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    return _route_defaults_from_metadata(metadata)


def _route_defaults_from_metadata(metadata: dict[str, Any]) -> dict[str, str]:
    trade_direction = str(metadata.get("trade_direction") or "")
    if trade_direction == "steam_to_buff_buy_order":
        return {
            "buy_platform": "STEAM",
            "buy_price_type": "listing",
            "sell_platform": "BUFF",
            "sell_price_type": "buy_order",
            "cash_destination": "reinvest",
        }
    if trade_direction == "buff_to_steam_sell":
        return {
            "buy_platform": "BUFF",
            "buy_price_type": "listing",
            "sell_platform": "STEAM",
            "sell_price_type": "listing",
            "cash_destination": "reinvest",
        }
    return {}

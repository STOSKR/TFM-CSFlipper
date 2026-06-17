"""Load MARL market episodes from versioned parquet datasets."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd  # type: ignore[import-untyped]

from packages.marl.market_env import MarketEpisodeStep


def load_market_episode_steps(
    path: Path | str,
    *,
    split: str = "train",
    limit: int | None = None,
) -> tuple[MarketEpisodeStep, ...]:
    source_path = Path(path)
    parquet_path = _parquet_path(source_path, split=split)
    route_defaults = _route_defaults(source_path)
    frame = pd.read_parquet(parquet_path)
    if limit is not None:
        frame = frame.head(limit)
    rows = (
        {**route_defaults, **dict(row)}
        for row in frame.sort_values(["observed_day", "item_id"]).to_dict(orient="records")
    )
    return tuple(MarketEpisodeStep.from_mapping(row) for row in rows)


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

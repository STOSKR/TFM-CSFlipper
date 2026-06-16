"""Load MARL market episodes from versioned parquet datasets."""

from __future__ import annotations

from pathlib import Path

import pandas as pd  # type: ignore[import-untyped]

from packages.marl.market_env import MarketEpisodeStep


def load_market_episode_steps(
    path: Path | str,
    *,
    split: str = "train",
    limit: int | None = None,
) -> tuple[MarketEpisodeStep, ...]:
    parquet_path = _parquet_path(Path(path), split=split)
    frame = pd.read_parquet(parquet_path)
    if limit is not None:
        frame = frame.head(limit)
    rows = (
        dict(row)
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

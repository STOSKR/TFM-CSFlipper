from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import datetime
from decimal import Decimal

import pytest

from apps.acquisition.platform_workers import PlatformWorkerResult, WorkerError
from apps.acquisition.steamdt_hanging import SteamDTCandidate
from apps.acquisition.streaming_pipeline import (
    StreamingPipelineConfig,
    iter_candidates,
    run_streaming_pipeline,
)
from packages.persistence.simple_market import SimpleMarketSnapshot


def _candidate(name: str, *, buff_url: str | None = None) -> SteamDTCandidate:
    return SteamDTCandidate(
        item_name=name,
        market_hash_name=f"{name} (Field-Tested)",
        quality="Field-Tested",
        buff_url=buff_url or f"https://buff.163.com/goods/{name}",
        steam_url=f"https://steamcommunity.com/market/listings/730/{name}",
    )


def _snapshot(candidate: SteamDTCandidate, scraped_at: datetime) -> SimpleMarketSnapshot:
    return SimpleMarketSnapshot(
        name=candidate.item_name,
        quality=candidate.quality or "Field-Tested",
        stattrak=candidate.stattrak,
        scraped_at=scraped_at,
        steam_price=Decimal("10.00"),
        steam_currency="CNY",
        buff_price=Decimal("8.00"),
        buff_currency="CNY",
    )


@pytest.mark.asyncio
async def test_streaming_pipeline_batches_and_persists_incrementally() -> None:
    candidates = (_candidate("A"), _candidate("B"), _candidate("C"))
    scraped_batches: list[tuple[str, ...]] = []
    persisted_batches: list[int] = []
    logs: list[str] = []

    async def scrape_batch(
        batch: tuple[SteamDTCandidate, ...],
    ) -> tuple[PlatformWorkerResult, ...]:
        scraped_batches.append(tuple(candidate.item_name for candidate in batch))
        return (PlatformWorkerResult(platform_id="steam", observations=()),)

    def build_snapshots(
        batch: tuple[SteamDTCandidate, ...],
        _results: tuple[PlatformWorkerResult, ...],
        scraped_at: datetime,
    ) -> tuple[SimpleMarketSnapshot, ...]:
        return tuple(_snapshot(candidate, scraped_at) for candidate in batch)

    async def persist_snapshots(snapshots: tuple[SimpleMarketSnapshot, ...]) -> None:
        persisted_batches.append(len(snapshots))

    summary = await run_streaming_pipeline(
        iter_candidates(candidates),
        scrape_batch=scrape_batch,
        build_snapshots=build_snapshots,
        persist_snapshots=persist_snapshots,
        config=StreamingPipelineConfig(batch_size=2, queue_maxsize=1),
        log=logs.append,
    )

    assert scraped_batches == [("A", "B"), ("C",)]
    assert "stream_batch_items=1 items=A (Field-Tested) | B (Field-Tested)" in logs
    assert "stream_batch_items=2 items=C (Field-Tested)" in logs
    assert persisted_batches == [2, 1]
    assert summary.candidates_seen == 3
    assert summary.batches_completed == 2
    assert summary.snapshots_persisted == 3


@pytest.mark.asyncio
async def test_streaming_pipeline_deduplicates_candidates() -> None:
    candidate = _candidate("A")

    async def scrape_batch(
        batch: tuple[SteamDTCandidate, ...],
    ) -> tuple[PlatformWorkerResult, ...]:
        assert batch == (candidate,)
        return ()

    def build_snapshots(
        batch: tuple[SteamDTCandidate, ...],
        _results: tuple[PlatformWorkerResult, ...],
        scraped_at: datetime,
    ) -> tuple[SimpleMarketSnapshot, ...]:
        return tuple(_snapshot(item, scraped_at) for item in batch)

    summary = await run_streaming_pipeline(
        iter_candidates((candidate, candidate)),
        scrape_batch=scrape_batch,
        build_snapshots=build_snapshots,
        config=StreamingPipelineConfig(batch_size=5, queue_maxsize=2),
    )

    assert summary.candidates_seen == 2
    assert summary.candidates_enqueued == 1
    assert summary.duplicates_skipped == 1
    assert summary.snapshots_built == 1


@pytest.mark.asyncio
async def test_streaming_pipeline_tracks_platform_errors() -> None:
    async def scrape_batch(
        _batch: tuple[SteamDTCandidate, ...],
    ) -> tuple[PlatformWorkerResult, ...]:
        return (
            PlatformWorkerResult(
                platform_id="buff163",
                observations=(),
                errors=(
                    WorkerError(
                        platform_id="buff163",
                        market_hash_name="bad",
                        message="not found",
                    ),
                ),
            ),
        )

    def build_snapshots(
        _batch: tuple[SteamDTCandidate, ...],
        _results: tuple[PlatformWorkerResult, ...],
        _scraped_at: datetime,
    ) -> tuple[SimpleMarketSnapshot, ...]:
        return ()

    summary = await run_streaming_pipeline(
        iter_candidates((_candidate("A"),)),
        scrape_batch=scrape_batch,
        build_snapshots=build_snapshots,
    )

    assert summary.errors_by_platform == {"buff163": 1}


@pytest.mark.asyncio
async def test_streaming_pipeline_can_cancel_after_persisted_batches() -> None:
    async def producer() -> AsyncIterator[SteamDTCandidate]:
        yield _candidate("A")
        raise asyncio.CancelledError

    async def scrape_batch(
        batch: tuple[SteamDTCandidate, ...],
    ) -> tuple[PlatformWorkerResult, ...]:
        assert len(batch) == 1
        return ()

    def build_snapshots(
        batch: tuple[SteamDTCandidate, ...],
        _results: tuple[PlatformWorkerResult, ...],
        scraped_at: datetime,
    ) -> tuple[SimpleMarketSnapshot, ...]:
        return tuple(_snapshot(candidate, scraped_at) for candidate in batch)

    persisted = 0

    async def persist_snapshots(snapshots: tuple[SimpleMarketSnapshot, ...]) -> None:
        nonlocal persisted
        persisted += len(snapshots)

    summary = await run_streaming_pipeline(
        producer(),
        scrape_batch=scrape_batch,
        build_snapshots=build_snapshots,
        persist_snapshots=persist_snapshots,
    )

    assert summary.cancelled is True
    assert persisted == 1
    assert summary.snapshots_persisted == 1

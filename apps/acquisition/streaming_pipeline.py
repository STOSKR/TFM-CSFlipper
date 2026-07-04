"""Local streaming pipeline primitives for candidate scraping."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterable, Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from apps.acquisition.platform_workers import PlatformWorkerResult
from apps.acquisition.steamdt_hanging import SteamDTCandidate
from packages.persistence.simple_market import SimpleMarketSnapshot

LogCallback = Callable[[str], None]
ScrapeBatch = Callable[
    [tuple[SteamDTCandidate, ...]],
    Awaitable[tuple[PlatformWorkerResult, ...]],
]
BuildSnapshots = Callable[
    [tuple[SteamDTCandidate, ...], tuple[PlatformWorkerResult, ...], datetime],
    tuple[SimpleMarketSnapshot, ...],
]
PersistSnapshots = Callable[[tuple[SimpleMarketSnapshot, ...]], Awaitable[Any]]


@dataclass(frozen=True, slots=True)
class StreamingPipelineConfig:
    batch_size: int = 10
    queue_maxsize: int = 10

    def __post_init__(self) -> None:
        if self.batch_size < 1:
            raise ValueError("batch_size must be at least 1")
        if self.queue_maxsize < 1:
            raise ValueError("queue_maxsize must be at least 1")


@dataclass(slots=True)
class StreamingPipelineSummary:
    candidates_seen: int = 0
    candidates_enqueued: int = 0
    duplicates_skipped: int = 0
    batches_completed: int = 0
    snapshots_built: int = 0
    snapshots_persisted: int = 0
    errors_by_platform: dict[str, int] = field(default_factory=dict)
    cancelled: bool = False


async def iter_candidates(
    candidates: tuple[SteamDTCandidate, ...],
) -> AsyncIterable[SteamDTCandidate]:
    for candidate in candidates:
        yield candidate
        await asyncio.sleep(0)


async def run_streaming_pipeline(
    producer: AsyncIterable[SteamDTCandidate],
    *,
    scrape_batch: ScrapeBatch,
    build_snapshots: BuildSnapshots,
    persist_snapshots: PersistSnapshots | None = None,
    config: StreamingPipelineConfig | None = None,
    log: LogCallback | None = None,
) -> StreamingPipelineSummary:
    pipeline_config = config or StreamingPipelineConfig()
    queue: asyncio.Queue[SteamDTCandidate | None] = asyncio.Queue(
        maxsize=pipeline_config.queue_maxsize
    )
    summary = StreamingPipelineSummary()
    seen: set[tuple[str, str | None, str | None]] = set()

    async def produce() -> None:
        try:
            async for candidate in producer:
                summary.candidates_seen += 1
                key = _candidate_key(candidate)
                if key in seen:
                    summary.duplicates_skipped += 1
                    _emit(log, f"stream_duplicate={candidate.market_hash_name}")
                    continue
                seen.add(key)
                await queue.put(candidate)
                summary.candidates_enqueued += 1
                _emit(log, f"stream_enqueued={candidate.market_hash_name}")
        except asyncio.CancelledError:
            summary.cancelled = True
        finally:
            await queue.put(None)

    async def consume() -> None:
        batch: list[SteamDTCandidate] = []
        while True:
            item = await queue.get()
            try:
                if item is None:
                    if batch:
                        await _process_batch(
                            tuple(batch),
                            scrape_batch=scrape_batch,
                            build_snapshots=build_snapshots,
                            persist_snapshots=persist_snapshots,
                            summary=summary,
                            log=log,
                        )
                    return
                batch.append(item)
                if len(batch) >= pipeline_config.batch_size:
                    await _process_batch(
                        tuple(batch),
                        scrape_batch=scrape_batch,
                        build_snapshots=build_snapshots,
                        persist_snapshots=persist_snapshots,
                        summary=summary,
                        log=log,
                    )
                    batch.clear()
            finally:
                queue.task_done()

    await asyncio.gather(produce(), consume())
    return summary


async def _process_batch(
    candidates: tuple[SteamDTCandidate, ...],
    *,
    scrape_batch: ScrapeBatch,
    build_snapshots: BuildSnapshots,
    persist_snapshots: PersistSnapshots | None,
    summary: StreamingPipelineSummary,
    log: LogCallback | None,
) -> None:
    batch_number = summary.batches_completed + 1
    _emit(log, f"stream_batch={batch_number} candidates={len(candidates)}")
    _emit(log, f"stream_batch_items={batch_number} items={_batch_items(candidates)}")
    results = await scrape_batch(candidates)
    snapshots = build_snapshots(candidates, results, datetime.now(tz=UTC))
    if persist_snapshots is not None and snapshots:
        await persist_snapshots(snapshots)
        summary.snapshots_persisted += len(snapshots)
    summary.batches_completed += 1
    summary.snapshots_built += len(snapshots)
    for result in results:
        summary.errors_by_platform[result.platform_id] = (
            summary.errors_by_platform.get(result.platform_id, 0) + len(result.errors)
        )
    _emit(log, f"stream_batch_done={batch_number} snapshots={len(snapshots)}")


def _candidate_key(candidate: SteamDTCandidate) -> tuple[str, str | None, str | None]:
    return (candidate.market_hash_name, candidate.buff_url, candidate.steam_url)


def _batch_items(candidates: tuple[SteamDTCandidate, ...]) -> str:
    return " | ".join(" ".join(candidate.market_hash_name.split()) for candidate in candidates)


def _emit(log: LogCallback | None, message: str) -> None:
    if log is not None:
        log(message)

"""Concurrent platform workers fed by SteamDT candidates."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

from apps.acquisition.buff163_market import (
    Buff163Candidate,
    Buff163Connector,
    Buff163ConnectorConfig,
    Buff163Observation,
)
from apps.acquisition.steam_browser_market import (
    SteamBrowserCandidate,
    SteamBrowserConnector,
    SteamBrowserConnectorConfig,
    SteamBrowserObservation,
)
from apps.acquisition.steam_market import (
    SteamMarketCandidate,
    SteamMarketConnector,
    SteamMarketConnectorConfig,
    SteamMarketObservation,
)
from apps.acquisition.steamdt_hanging import SteamDTCandidate

LogCallback = Any


@dataclass(frozen=True, slots=True)
class WorkerError:
    platform_id: str
    market_hash_name: str
    message: str
    debug_log: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PlatformWorkerResult:
    platform_id: str
    observations: tuple[
        SteamMarketObservation | SteamBrowserObservation | Buff163Observation,
        ...,
    ]
    errors: tuple[WorkerError, ...] = ()


@dataclass(frozen=True, slots=True)
class PlatformWorkerConfig:
    fetch_steam: bool = True
    fetch_buff: bool = True
    steam_browser: bool = True
    steam_config: SteamMarketConnectorConfig = field(default_factory=SteamMarketConnectorConfig)
    steam_browser_config: SteamBrowserConnectorConfig = field(
        default_factory=SteamBrowserConnectorConfig
    )
    buff_config: Buff163ConnectorConfig = field(default_factory=Buff163ConnectorConfig)


async def scrape_candidate_platforms(
    candidates: tuple[SteamDTCandidate, ...],
    *,
    config: PlatformWorkerConfig | None = None,
    correlation_id: str | None = None,
    log: LogCallback | None = None,
) -> tuple[PlatformWorkerResult, ...]:
    worker_config = config or PlatformWorkerConfig()
    run_id = correlation_id or f"platforms:{uuid4()}"
    tasks = []
    if worker_config.fetch_steam:
        if worker_config.steam_browser:
            tasks.append(
                _scrape_steam_browser(
                    candidates,
                    config=worker_config.steam_browser_config,
                    correlation_id=run_id,
                    log=log,
                )
            )
        else:
            tasks.append(
                _scrape_steam_api(
                    candidates,
                    config=worker_config.steam_config,
                    correlation_id=run_id,
                    log=log,
                )
            )
    if worker_config.fetch_buff:
        tasks.append(
            _scrape_buff(
                candidates,
                config=worker_config.buff_config,
                correlation_id=run_id,
                log=log,
            )
        )
    if not tasks:
        return ()
    return tuple(await asyncio.gather(*tasks))


def load_steamdt_candidates(path: Path) -> tuple[SteamDTCandidate, ...]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, list):
        raise ValueError("SteamDT candidate JSON must be a list")
    return tuple(_candidate_from_row(row) for row in payload if isinstance(row, dict))


def latest_steamdt_candidates_path(
    directory: Path = Path("data/flow-runs"),
    *,
    pattern: str = "steamdt_candidates_*.json",
) -> Path:
    candidates = [path for path in directory.glob(pattern) if path.is_file()]
    if not candidates:
        raise FileNotFoundError(
            f"no SteamDT candidate JSON found in {directory} matching {pattern}"
        )
    return max(candidates, key=lambda path: (path.stat().st_mtime, path.name))


def worker_results_to_jsonable(results: tuple[PlatformWorkerResult, ...]) -> dict[str, Any]:
    return {
        "observations": [
            record.observation.model_dump(mode="json")
            for result in results
            for record in result.observations
        ],
        "errors": [
            {
                "platform_id": error.platform_id,
                "market_hash_name": error.market_hash_name,
                "message": error.message,
                "debug_log": list(error.debug_log),
            }
            for result in results
            for error in result.errors
        ],
        "summary": {
            result.platform_id: {
                "observations": len(result.observations),
                "errors": len(result.errors),
            }
            for result in results
        },
    }


async def _scrape_steam_api(
    candidates: tuple[SteamDTCandidate, ...],
    *,
    config: SteamMarketConnectorConfig,
    correlation_id: str,
    log: LogCallback | None,
) -> PlatformWorkerResult:
    steam_candidates = [
        SteamMarketCandidate(
            market_hash_name=candidate.market_hash_name,
            asset_name=candidate.item_name,
            quality=candidate.quality,
            stattrak=candidate.stattrak,
        )
        for candidate in candidates
        if candidate.market_hash_name
    ]
    observations: list[SteamMarketObservation] = []
    errors: list[WorkerError] = []
    semaphore = asyncio.Semaphore(config.max_concurrency)

    async with SteamMarketConnector(config=config) as connector:

        async def fetch_one(candidate: SteamMarketCandidate) -> None:
            async with semaphore:
                try:
                    observations.append(
                        await connector.fetch_price_overview(
                            candidate,
                            correlation_id=correlation_id,
                        )
                    )
                except Exception as exc:
                    _emit(log, f"[steam-api] {candidate.market_hash_name}: ERROR {exc}")
                    errors.append(
                        WorkerError(
                            platform_id="steam",
                            market_hash_name=candidate.market_hash_name,
                            message=str(exc),
                        )
                    )

        await asyncio.gather(*(fetch_one(candidate) for candidate in steam_candidates))

    return PlatformWorkerResult("steam", tuple(observations), tuple(errors))


async def _scrape_steam_browser(
    candidates: tuple[SteamDTCandidate, ...],
    *,
    config: SteamBrowserConnectorConfig,
    correlation_id: str,
    log: LogCallback | None,
) -> PlatformWorkerResult:
    steam_candidates = [
        SteamBrowserCandidate(
            market_hash_name=candidate.market_hash_name,
            steam_url=candidate.steam_url,
            asset_name=candidate.item_name,
            quality=candidate.quality,
            stattrak=candidate.stattrak,
        )
        for candidate in candidates
        if candidate.market_hash_name
    ]
    connector = SteamBrowserConnector(config, log=log)
    try:
        observations, steam_errors = await connector.fetch_candidates_lenient(
            steam_candidates,
            correlation_id=correlation_id,
        )
    except Exception as exc:
        return PlatformWorkerResult(
            "steam",
            (),
            tuple(
                WorkerError(
                    platform_id="steam",
                    market_hash_name=candidate.market_hash_name,
                    message=str(exc),
                )
                for candidate in steam_candidates
            ),
        )
    errors = [
        WorkerError(
            platform_id="steam",
            market_hash_name=error.candidate.market_hash_name,
            message=error.message,
            debug_log=error.debug_log,
        )
        for error in steam_errors
    ]
    return PlatformWorkerResult("steam", tuple(observations), tuple(errors))


async def _scrape_buff(
    candidates: tuple[SteamDTCandidate, ...],
    *,
    config: Buff163ConnectorConfig,
    correlation_id: str,
    log: LogCallback | None,
) -> PlatformWorkerResult:
    buff_candidates = [
        Buff163Candidate(
            market_hash_name=candidate.market_hash_name,
            buff_url=candidate.buff_url,
            asset_name=candidate.item_name,
            quality=candidate.quality,
            stattrak=candidate.stattrak,
        )
        for candidate in candidates
        if candidate.market_hash_name and candidate.buff_url
    ]
    connector = Buff163Connector(config, log=log)
    try:
        observations, buff_errors = await connector.fetch_candidates_lenient(
            buff_candidates,
            correlation_id=correlation_id,
        )
    except Exception as exc:
        return PlatformWorkerResult(
            "buff163",
            (),
            tuple(
                WorkerError(
                    platform_id="buff163",
                    market_hash_name=candidate.market_hash_name,
                    message=str(exc),
                )
                for candidate in buff_candidates
            ),
        )
    errors = [
        WorkerError(
            platform_id="buff163",
            market_hash_name=error.candidate.market_hash_name,
            message=error.message,
            debug_log=error.debug_log,
        )
        for error in buff_errors
    ]

    return PlatformWorkerResult("buff163", tuple(observations), tuple(errors))


def _candidate_from_row(row: dict[str, Any]) -> SteamDTCandidate:
    return SteamDTCandidate(
        item_name=str(row.get("item_name") or ""),
        market_hash_name=str(row.get("market_hash_name") or ""),
        display_name=_optional_str(row.get("display_name")),
        quality=_optional_str(row.get("quality")),
        stattrak=bool(row.get("stattrak", False)),
        item_url=_optional_str(row.get("item_url")),
        buff_url=_optional_str(row.get("buff_url")),
        steam_url=_optional_str(row.get("steam_url")),
        currency=_optional_str(row.get("currency")),
    )


def _optional_str(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _emit(log: LogCallback | None, message: str) -> None:
    if log:
        log(message)

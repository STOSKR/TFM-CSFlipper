"""Streaming local pipeline for SteamDT candidates and platform workers."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from apps.acquisition.buff_market import BuffConnectorConfig
from apps.acquisition.platform_workers import (
    PlatformWorkerConfig,
    PlatformWorkerResult,
    latest_steamdt_candidates_path,
    load_steamdt_candidates,
    scrape_candidate_platforms,
)
from apps.acquisition.steam_browser_market import SteamBrowserConnectorConfig
from apps.acquisition.steam_market import SteamMarketConnectorConfig
from apps.acquisition.steamdt_hanging import SteamDTCandidate
from apps.acquisition.streaming_pipeline import (
    StreamingPipelineConfig,
    iter_candidates,
    run_streaming_pipeline,
)
from apps.cli.scrape_candidate_platforms import (
    build_simple_market_snapshots,
    persist_simple_market_snapshots,
    simple_results_to_jsonable,
)
from packages.persistence.simple_market import SimpleMarketSnapshot
from packages.runtime_config import load_runtime_config


async def run(args: argparse.Namespace) -> int:
    logger, log_path = _configure_logging(args.log_file)
    print(f"log_file={log_path}")
    candidates_path = args.candidates or latest_steamdt_candidates_path(args.candidates_dir)
    print(f"candidates_file={candidates_path}")
    candidates = load_steamdt_candidates(candidates_path)
    print(f"candidates_loaded={len(candidates)}")

    worker_config = _worker_config(args)
    all_results: list[PlatformWorkerResult] = []
    all_snapshots: list[SimpleMarketSnapshot] = []

    async def scrape_batch(
        batch: tuple[SteamDTCandidate, ...],
    ) -> tuple[PlatformWorkerResult, ...]:
        results = await scrape_candidate_platforms(
            batch,
            config=worker_config,
            log=logger.info,
        )
        all_results.extend(results)
        return results

    def build_snapshots(
        batch: tuple[SteamDTCandidate, ...],
        results: tuple[PlatformWorkerResult, ...],
        scraped_at: Any,
    ) -> tuple[SimpleMarketSnapshot, ...]:
        snapshots = build_simple_market_snapshots(batch, results, scraped_at=scraped_at)
        all_snapshots.extend(snapshots)
        return snapshots

    summary = await run_streaming_pipeline(
        iter_candidates(candidates),
        scrape_batch=scrape_batch,
        build_snapshots=build_snapshots,
        persist_snapshots=(
            persist_simple_market_snapshots if args.persist and not args.dry_run else None
        ),
        config=StreamingPipelineConfig(
            batch_size=args.batch_size,
            queue_maxsize=args.queue_size,
        ),
        log=logger.info,
    )

    payload = simple_results_to_jsonable(tuple(all_snapshots), tuple(all_results))
    output_path = args.output or _default_output_path()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(
        "stream_done: "
        f"seen={summary.candidates_seen} "
        f"enqueued={summary.candidates_enqueued} "
        f"duplicates={summary.duplicates_skipped} "
        f"batches={summary.batches_completed} "
        f"snapshots={summary.snapshots_built} "
        f"persisted={summary.snapshots_persisted}"
    )
    print(f"output_file={output_path}")
    logger.info("stream_summary=%s", summary)
    logger.info("platform_observations_file=%s", output_path)
    return 0


def main() -> None:
    runtime_config = load_runtime_config()
    parser = argparse.ArgumentParser(
        description="Stream SteamDT candidates through platform workers."
    )
    parser.add_argument("--candidates", type=Path)
    parser.add_argument("--candidates-dir", type=Path, default=Path("data/flow-runs"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--steam", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--buff", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument(
        "--concurrent-platforms",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument("--show-browser", action="store_true")
    parser.add_argument("--steam-api", action="store_true")
    parser.add_argument("--steam-login", action="store_true")
    parser.add_argument("--steam-login-wait", type=int, default=120)
    parser.add_argument(
        "--steam-session-state",
        type=Path,
        default=Path("data/browser-state/steam_storage_state.json"),
    )
    parser.add_argument("--no-steam-session-state", action="store_true")
    parser.add_argument("--buff-login", action="store_true")
    parser.add_argument("--buff-login-wait", type=int, default=120)
    parser.add_argument(
        "--buff-session-state",
        type=Path,
        default=Path("data/browser-state/buff_storage_state.json"),
    )
    parser.add_argument("--no-buff-session-state", action="store_true")
    parser.add_argument(
        "--steam-concurrency",
        type=int,
        default=runtime_config.workers.steam_concurrency,
    )
    parser.add_argument(
        "--buff-concurrency",
        type=int,
        default=runtime_config.workers.buff_concurrency,
    )
    parser.add_argument(
        "--steam-min-delay",
        type=float,
        default=runtime_config.delays.steam_min_seconds,
    )
    parser.add_argument(
        "--steam-max-delay",
        type=float,
        default=runtime_config.delays.steam_max_seconds,
    )
    parser.add_argument(
        "--buff-min-delay",
        type=float,
        default=runtime_config.delays.buff_min_seconds,
    )
    parser.add_argument(
        "--buff-max-delay",
        type=float,
        default=runtime_config.delays.buff_max_seconds,
    )
    parser.add_argument("--batch-size", type=int, default=runtime_config.workers.batch_size)
    parser.add_argument("--queue-size", type=int, default=10)
    parser.add_argument("--log-file", type=Path)
    parser.add_argument("--persist", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    asyncio.run(run(args))


def _worker_config(args: argparse.Namespace) -> PlatformWorkerConfig:
    return PlatformWorkerConfig(
        fetch_steam=args.steam,
        fetch_buff=args.buff,
        steam_browser=not args.steam_api,
        concurrent_platforms=args.concurrent_platforms,
        steam_config=SteamMarketConnectorConfig(
            max_concurrency=args.steam_concurrency,
            min_delay_seconds=args.steam_min_delay,
            max_delay_seconds=args.steam_max_delay,
        ),
        steam_browser_config=SteamBrowserConnectorConfig(
            headless=not args.show_browser,
            manual_login_wait_ms=args.steam_login_wait * 1000 if args.steam_login else 0,
            session_state_path=None if args.no_steam_session_state else args.steam_session_state,
            max_concurrency=args.steam_concurrency,
            min_delay_seconds=args.steam_min_delay,
            max_delay_seconds=args.steam_max_delay,
        ),
        buff_config=BuffConnectorConfig(
            headless=not args.show_browser,
            manual_login_wait_ms=args.buff_login_wait * 1000 if args.buff_login else 0,
            session_state_path=None if args.no_buff_session_state else args.buff_session_state,
            max_concurrency=args.buff_concurrency,
            min_delay_seconds=args.buff_min_delay,
            max_delay_seconds=args.buff_max_delay,
        ),
    )


def _configure_logging(log_file: Path | None) -> tuple[logging.Logger, Path]:
    log_path = log_file or _default_log_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("csflipper.streaming_scrape")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    return logger, log_path


def _default_output_path() -> Path:
    from datetime import UTC, datetime

    run_id = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S")
    return Path("data/flow-runs") / f"stream_platform_observations_{run_id}.json"


def _default_log_path() -> Path:
    from datetime import UTC, datetime

    run_id = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S")
    return Path("logs") / f"stream_market_workers_{run_id}.log"


if __name__ == "__main__":
    main()

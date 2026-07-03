"""Render-friendly streaming scrape flow without intermediate candidate JSON."""

from __future__ import annotations

import argparse
import asyncio
import subprocess
import sys
from collections.abc import AsyncIterator
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from apps.acquisition.buff163_market import Buff163ConnectorConfig
from apps.acquisition.platform_workers import (
    PlatformWorkerConfig,
    PlatformWorkerResult,
    scrape_candidate_platforms,
)
from apps.acquisition.steam_browser_market import SteamBrowserConnectorConfig
from apps.acquisition.steam_market import SteamMarketConnectorConfig
from apps.acquisition.steamdt_hanging import (
    SteamDTCandidate,
    SteamDTHangingDiscovery,
    SteamDTHangingFilters,
)
from apps.acquisition.streaming_pipeline import StreamingPipelineConfig, run_streaming_pipeline
from apps.cli.discover_steamdt_hanging import _selected_profiles, _tag_candidates
from apps.cli.scrape_candidate_platforms import (
    build_simple_market_snapshots,
    persist_simple_market_snapshots,
)
from packages.persistence.simple_market import SimpleMarketSnapshot
from packages.runtime_config import load_runtime_config


async def run(args: argparse.Namespace) -> int:
    worker_config = _worker_config(args)

    async def scrape_batch(
        batch: tuple[SteamDTCandidate, ...],
    ) -> tuple[PlatformWorkerResult, ...]:
        print(f"stream_scrape_batch candidates={len(batch)}", flush=True)
        return await scrape_candidate_platforms(batch, config=worker_config, progress_log=print)

    def build_snapshots(
        batch: tuple[SteamDTCandidate, ...],
        results: tuple[PlatformWorkerResult, ...],
        scraped_at: datetime,
    ) -> tuple[SimpleMarketSnapshot, ...]:
        return build_simple_market_snapshots(batch, results, scraped_at=scraped_at)

    summary = await run_streaming_pipeline(
        _iter_steamdt_candidates(args),
        scrape_batch=scrape_batch,
        build_snapshots=build_snapshots,
        persist_snapshots=(
            persist_simple_market_snapshots if args.persist and not args.dry_run else None
        ),
        config=StreamingPipelineConfig(
            batch_size=args.batch_size,
            queue_maxsize=args.queue_size,
        ),
        log=lambda message: print(message, flush=True),
    )
    print(
        "render_stream_done "
        f"seen={summary.candidates_seen} enqueued={summary.candidates_enqueued} "
        f"duplicates={summary.duplicates_skipped} batches={summary.batches_completed} "
        f"snapshots={summary.snapshots_built} persisted={summary.snapshots_persisted}",
        flush=True,
    )
    if summary.candidates_enqueued == 0:
        return 124
    if args.refresh:
        refresh_code = _run_refresh(args)
        if refresh_code != 0:
            return refresh_code
    if args.score:
        return _run_score(args)
    return 0


async def _iter_steamdt_candidates(args: argparse.Namespace) -> AsyncIterator[SteamDTCandidate]:
    runtime_config = load_runtime_config()
    profile_items = _selected_profiles(args, runtime_config.steamdt)
    for strategy_id, profile in profile_items:
        balance_type = args.balance_type or profile.balance_type
        buy_mode = args.buy_mode if args.buy_mode is not None else profile.buy_mode
        sell_mode = args.sell_mode or profile.sell_mode
        emitted_for_profile = 0
        filters = SteamDTHangingFilters(
            headless=not args.show_browser,
            max_candidates=args.limit or runtime_config.discovery.candidates_limit,
            min_price=(
                Decimal(str(args.min_price))
                if args.min_price is not None
                else runtime_config.discovery.min_price
            ),
            max_price=Decimal(str(args.max_price)) if args.max_price is not None else None,
            min_volume=(
                args.min_volume
                if args.min_volume is not None
                else runtime_config.discovery.min_volume
            ),
            currency_code=args.currency,
            balance_type=balance_type,
            sell_mode=sell_mode,
            buy_mode=buy_mode,
            platform_buff=args.platform_buff,
            platform_c5game=args.platform_c5game,
            platform_uu=args.platform_uu,
            timeout_ms=args.steamdt_timeout * 1000,
            navigation_retries=args.steamdt_retries,
            session_state_path=None if args.no_session_state else args.session_state,
            steam_sale_fee_rate=Decimal(str(args.steam_fee_percent)) / Decimal("100"),
            withdrawal_fee_rate=(
                Decimal(str(args.withdrawal_fee_percent)) / Decimal("100")
                if args.withdrawal_fee_percent is not None
                else runtime_config.fees.withdrawal_percent_for_balance(balance_type)
                / Decimal("100")
            ),
        )
        print(
            "render_stream_strategy="
            f"{strategy_id} balance={balance_type} buy={buy_mode or '-'} sell={sell_mode}",
            flush=True,
        )
        try:
            candidates = await asyncio.wait_for(
                SteamDTHangingDiscovery(filters, progress_log=_print_progress).discover(),
                timeout=args.steamdt_profile_timeout,
            )
        except TimeoutError:
            print(
                f"render_stream_strategy={strategy_id} status=timeout "
                f"profile_timeout_seconds={args.steamdt_profile_timeout}",
                flush=True,
            )
            continue
        for candidate in _tag_candidates(
            candidates,
            strategy_id=strategy_id,
            balance_type=balance_type,
            buy_mode=buy_mode,
            sell_mode=sell_mode,
        ):
            if args.limit is not None and emitted_for_profile >= args.limit:
                break
            emitted_for_profile += 1
            print(f"render_stream_candidate={candidate.market_hash_name}", flush=True)
            yield candidate


def _run_refresh(args: argparse.Namespace) -> int:
    command = [
        sys.executable,
        "-u",
        "-m",
        "apps.cli.refresh_market_history",
        "--stale-minutes",
        str(args.stale_minutes),
    ]
    if args.refresh_limit is not None:
        command.extend(["--limit", str(args.refresh_limit)])
    if args.persist:
        command.append("--persist")
    else:
        command.append("--dry-run")
    if args.show_browser:
        command.append("--show-browser")
    if args.concurrent_platforms:
        command.append("--concurrent-platforms")
    else:
        command.append("--no-concurrent-platforms")
    print("render_stream_step=refresh", flush=True)
    print(" ".join(command), flush=True)
    return subprocess.run(command, check=False).returncode


def _run_score(args: argparse.Namespace) -> int:
    command = [
        sys.executable,
        "-u",
        "-m",
        "apps.cli.score_live_opportunities",
    ]
    if not args.persist:
        command.append("--dry-run")
    print("render_stream_step=score", flush=True)
    print(" ".join(command), flush=True)
    return subprocess.run(command, check=False).returncode


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
            session_state_path=None if args.no_steam_session_state else args.steam_session_state,
            max_concurrency=args.steam_concurrency,
            min_delay_seconds=args.steam_min_delay,
            max_delay_seconds=args.steam_max_delay,
        ),
        buff_config=Buff163ConnectorConfig(
            headless=not args.show_browser,
            session_state_path=None if args.no_buff_session_state else args.buff_session_state,
            max_concurrency=args.buff_concurrency,
            min_delay_seconds=args.buff_min_delay,
            max_delay_seconds=args.buff_max_delay,
        ),
    )


def _print_progress(message: str) -> None:
    print(message, flush=True)


def main() -> None:
    runtime_config = load_runtime_config()
    parser = build_parser(runtime_config)
    args = parser.parse_args()
    if args.fast:
        args.profile = "platform_arbitrage_fast"
    raise SystemExit(asyncio.run(run(args)))


def build_parser(runtime_config: Any) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render streaming scrape pipeline.")
    parser.add_argument(
        "limit",
        nargs="?",
        type=int,
        default=runtime_config.discovery.candidates_limit,
    )
    parser.add_argument(
        "--profile",
        choices=tuple(runtime_config.steamdt.profiles),
        default=runtime_config.steamdt.default_profile,
    )
    parser.add_argument("--fast", action="store_true", help="Use platform_arbitrage_fast profile")
    parser.add_argument(
        "--all-profiles",
        action=argparse.BooleanOptionalAction,
        default=runtime_config.steamdt.run_all_profiles,
    )
    parser.add_argument("--batch-size", type=int, default=runtime_config.workers.batch_size)
    parser.add_argument("--queue-size", type=int, default=2)
    parser.add_argument("--steamdt-timeout", type=int, default=30)
    parser.add_argument("--steamdt-retries", type=int, default=1)
    parser.add_argument("--steamdt-profile-timeout", type=int, default=120)
    parser.add_argument("--currency", default=runtime_config.discovery.currency)
    parser.add_argument("--min-price", "--min", dest="min_price", type=float)
    parser.add_argument("--max-price", "--max", dest="max_price", type=float)
    parser.add_argument("--min-volume", "--vol", dest="min_volume", type=int)
    parser.add_argument("--balance-type")
    parser.add_argument("--sell-mode")
    parser.add_argument("--buy-mode")
    parser.add_argument("--platform-buff", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--platform-c5game", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--platform-uu", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument(
        "--session-state",
        type=Path,
        default=Path("data/browser-state/steamdt_storage_state.json"),
    )
    parser.add_argument("--no-session-state", action="store_true")
    parser.add_argument("--steam", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--buff", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument(
        "--concurrent-platforms",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument("--steam-api", action="store_true")
    parser.add_argument("--show-browser", action="store_true")
    parser.add_argument(
        "--steam-session-state",
        type=Path,
        default=Path("data/browser-state/steam_storage_state.json"),
    )
    parser.add_argument("--no-steam-session-state", action="store_true")
    parser.add_argument(
        "--buff-session-state",
        type=Path,
        default=Path("data/browser-state/buff163_storage_state.json"),
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
    parser.add_argument(
        "--steam-fee-percent",
        type=float,
        default=float(runtime_config.fees.steam_sale_percent),
    )
    parser.add_argument("--withdrawal-fee-percent", type=float)
    parser.add_argument("--refresh", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--stale-minutes", type=int, default=480)
    parser.add_argument("--refresh-limit", type=int)
    parser.add_argument(
        "--score",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Run live opportunity scoring after scraping and optional refresh.",
    )
    parser.add_argument("--persist", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--dry-run", action="store_true")
    return parser


if __name__ == "__main__":
    main()

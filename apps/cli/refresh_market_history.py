"""Refresh current and historical market data for items already stored in DB."""

from __future__ import annotations

import argparse
import asyncio
import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from apps.acquisition.buff163_market import Buff163ConnectorConfig
from apps.acquisition.platform_workers import PlatformWorkerConfig, scrape_candidate_platforms
from apps.acquisition.steam_browser_market import SteamBrowserConnectorConfig
from apps.acquisition.steam_market import SteamMarketConnectorConfig
from apps.acquisition.steamdt_hanging import SteamDTCandidate
from apps.cli.scrape_candidate_platforms import (
    build_simple_market_snapshots,
    simple_results_to_jsonable,
)
from packages.domain.market_parsing import market_hash_name
from packages.persistence.connection import create_pool
from packages.persistence.simple_market import SimpleMarketSnapshotRepository
from packages.runtime_config import load_runtime_config


async def run(args: argparse.Namespace) -> int:
    candidates = await load_market_item_candidates(limit=args.limit)
    print(f"market_items_loaded={len(candidates)}")
    buff_history_days = args.buff_history_days
    if args.buff and buff_history_days is None:
        buff_history_days = await recommended_buff_history_days(
            limit=args.limit,
            max_days=args.buff_history_max_days,
        )
    if args.buff:
        print(f"buff_history_days={buff_history_days}")
    config = _worker_config(args, buff_history_days=buff_history_days)
    results = await scrape_candidate_platforms(candidates, config=config, log=print)
    snapshots = build_simple_market_snapshots(
        candidates,
        results,
        scraped_at=datetime.now(tz=UTC),
    )

    if args.persist and not args.dry_run:
        pool = await create_pool(max_size=2)
        try:
            async with pool.acquire() as connection:
                await SimpleMarketSnapshotRepository(connection).record_snapshots(snapshots)
        finally:
            await pool.close()

    payload = simple_results_to_jsonable(snapshots, results)
    output_path = args.output or _default_output_path()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"snapshots={len(snapshots)}")
    print(f"mode={'persisted' if args.persist and not args.dry_run else 'dry_run'}")
    print(f"output_file={output_path}")
    return len(snapshots)


async def load_market_item_candidates(*, limit: int | None = None) -> tuple[SteamDTCandidate, ...]:
    pool = await create_pool(max_size=2)
    try:
        async with pool.acquire() as connection:
            rows = await connection.fetch(
                """
                select name, quality, stattrak, steam_url, buff_url
                from market_items
                where steam_url is not null or buff_url is not null
                order by updated_at desc nulls last, created_at desc
                limit $1
                """,
                limit,
            )
    finally:
        await pool.close()
    return tuple(candidate_from_market_item_row(dict(row)) for row in rows)


async def recommended_buff_history_days(
    *,
    limit: int | None = None,
    max_days: int = 365,
    now: datetime | None = None,
) -> int:
    pool = await create_pool(max_size=2)
    try:
        async with pool.acquire() as connection:
            row = await connection.fetchrow(
                """
                with items as (
                    select id
                    from market_items
                    where buff_url is not null
                    order by updated_at desc nulls last, created_at desc
                    limit $1
                ),
                latest as (
                    select
                        item_id,
                        max(observed_at) as latest_observed_at
                    from market_history_points
                    where platform_id = 'buff163'
                      and metric_name in (
                        'sell_price',
                        'buy_order_price',
                        'listing_count'
                      )
                    group by item_id
                )
                select
                    count(items.id) as item_count,
                    count(latest.latest_observed_at) as latest_count,
                    min(latest.latest_observed_at) as oldest_latest_observed_at
                from items
                left join latest on latest.item_id = items.id
                """,
                limit,
            )
    finally:
        await pool.close()
    return buff_history_days_from_db_row(row, max_days=max_days, now=now)


def buff_history_days_from_db_row(
    row: Any,
    *,
    max_days: int = 365,
    now: datetime | None = None,
) -> int:
    capped_max_days = max(1, max_days)
    if row is None:
        return capped_max_days
    item_count = int(row["item_count"] or 0)
    latest_count = int(row["latest_count"] or 0)
    oldest_latest = row["oldest_latest_observed_at"]
    if item_count == 0:
        return capped_max_days
    if latest_count < item_count or not isinstance(oldest_latest, datetime):
        return capped_max_days
    current_time = now or datetime.now(tz=UTC)
    latest_utc = (
        oldest_latest.astimezone(UTC)
        if oldest_latest.tzinfo
        else oldest_latest.replace(tzinfo=UTC)
    )
    elapsed_days = math.ceil(max(0.0, (current_time - latest_utc).total_seconds()) / 86400)
    return min(capped_max_days, max(1, elapsed_days + 1))


def candidate_from_market_item_row(row: dict[str, Any]) -> SteamDTCandidate:
    name = str(row.get("name") or "").strip()
    quality = _optional_str(row.get("quality"))
    stattrak = bool(row.get("stattrak", False))
    return SteamDTCandidate(
        item_name=name,
        market_hash_name=market_hash_name(name, quality),
        quality=quality,
        stattrak=stattrak,
        steam_url=_optional_str(row.get("steam_url")),
        buff_url=_optional_str(row.get("buff_url")),
    )


def _worker_config(
    args: argparse.Namespace,
    *,
    buff_history_days: int | None = None,
) -> PlatformWorkerConfig:
    return PlatformWorkerConfig(
        fetch_steam=args.steam,
        fetch_buff=args.buff,
        steam_browser=not args.steam_api,
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
        buff_config=Buff163ConnectorConfig(
            headless=not args.show_browser,
            manual_login_wait_ms=args.buff_login_wait * 1000 if args.buff_login else 0,
            session_state_path=None if args.no_buff_session_state else args.buff_session_state,
            history_days=buff_history_days or args.buff_history_max_days,
            max_concurrency=args.buff_concurrency,
            min_delay_seconds=args.buff_min_delay,
            max_delay_seconds=args.buff_max_delay,
        ),
    )


def _default_output_path() -> Path:
    run_id = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S")
    return Path("data/flow-runs") / f"market_history_refresh_{run_id}.json"


def _optional_str(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def main() -> None:
    runtime_config = load_runtime_config()
    parser = argparse.ArgumentParser(
        description="Refresh all stored market items using Steam and BUFF workers."
    )
    parser.add_argument("--limit", type=int)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--steam", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--buff", action=argparse.BooleanOptionalAction, default=True)
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
    parser.add_argument("--buff-history-days", type=int)
    parser.add_argument("--buff-history-max-days", type=int, default=365)
    parser.add_argument("--persist", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()

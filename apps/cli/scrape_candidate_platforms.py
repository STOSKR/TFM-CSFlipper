"""CLI command for scraping SteamDT candidates on Steam Market and BUFF."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from apps.acquisition.buff163_market import Buff163ConnectorConfig
from apps.acquisition.platform_workers import (
    PlatformWorkerConfig,
    PlatformWorkerResult,
    latest_steamdt_candidates_path,
    load_steamdt_candidates,
    scrape_candidate_platforms,
)
from apps.acquisition.steam_browser_market import SteamBrowserConnectorConfig
from apps.acquisition.steam_market import SteamMarketConnectorConfig
from apps.acquisition.steamdt_hanging import (
    SteamDTCandidate,
)
from packages.domain.market_parsing import quality_from_market_hash
from packages.persistence.connection import create_pool
from packages.persistence.simple_market import (
    SimpleMarketSnapshot,
    SimpleMarketSnapshotRepository,
)
from packages.runtime_config import load_runtime_config


async def run(args: argparse.Namespace) -> int:
    logger, log_path = _configure_logging(args)
    print(f"log_file={log_path}")
    if args.login_only:
        return await _save_login_states(args, logger)

    candidates_path = args.candidates or latest_steamdt_candidates_path(args.candidates_dir)
    print(f"candidates_file={candidates_path}")
    logger.info("steamdt_candidates_file=%s", candidates_path)
    candidates = load_steamdt_candidates(candidates_path)
    logger.info("loaded_candidates=%s", len(candidates))
    print(f"candidates_loaded={len(candidates)}")
    config = PlatformWorkerConfig(
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
            max_concurrency=args.buff_concurrency,
            min_delay_seconds=args.buff_min_delay,
            max_delay_seconds=args.buff_max_delay,
        ),
    )
    all_results: list[PlatformWorkerResult] = []
    all_snapshots: list[SimpleMarketSnapshot] = []
    for batch_index, batch in enumerate(_chunks(candidates, args.batch_size), start=1):
        logger.info("scraping_batch=%s size=%s", batch_index, len(batch))
        print(f"batch {batch_index}: candidates={len(batch)}")
        batch_results = await scrape_candidate_platforms(batch, config=config, log=logger.info)
        batch_snapshots = build_simple_market_snapshots(
            batch,
            batch_results,
            scraped_at=datetime.now(tz=UTC),
        )
        if args.persist and not args.dry_run:
            await _persist_snapshots(batch_snapshots)
            print(f"batch {batch_index}: persisted_snapshots={len(batch_snapshots)}")
        _print_batch_summary(batch_index, len(batch_snapshots), batch_results)
        all_results.extend(batch_results)
        all_snapshots.extend(batch_snapshots)

    results = tuple(all_results)
    snapshots = tuple(all_snapshots)
    payload = simple_results_to_jsonable(snapshots, results)

    output_path = args.output or _default_output_path()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    logger.info("platform_observations_file=%s", output_path)

    _print_final_summary(
        output_path=output_path,
        snapshots=len(snapshots),
        summary=payload["summary"],
        persisted=args.persist and not args.dry_run,
    )
    for platform_id, summary in payload["summary"].items():
        logger.info(
            "%s_worker=observations:%s errors:%s",
            platform_id,
            summary["observations"],
            summary["errors"],
        )
    for result in results:
        for error in result.errors:
            logger.error(
                "%s_error item=%s message=%s debug=%s",
                error.platform_id,
                error.market_hash_name,
                error.message,
                " | ".join(error.debug_log[-6:]),
            )
    return len(snapshots)


def main() -> None:
    runtime_config = load_runtime_config()
    parser = argparse.ArgumentParser(
        description="Scrape candidate prices with one worker per platform."
    )
    parser.add_argument(
        "--candidates",
        type=Path,
        help="SteamDT candidates JSON. Defaults to the latest file in --candidates-dir.",
    )
    parser.add_argument(
        "--candidates-dir",
        type=Path,
        default=Path("data/flow-runs"),
        help="Directory used to find the latest steamdt_candidates_*.json",
    )
    parser.add_argument("--output", type=Path, help="Where to write combined worker results")
    parser.add_argument("--steam", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--buff", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--show-browser", action="store_true", help="Show browser workers")
    parser.add_argument(
        "--login-only",
        action="store_true",
        help="Open selected platforms for login, save cookies, and exit without scraping",
    )
    parser.add_argument(
        "--login-wait",
        type=int,
        default=180,
        help="Seconds to wait before saving cookies in --login-only mode",
    )
    parser.add_argument(
        "--steam-api",
        action="store_true",
        help="Use the old Steam priceoverview HTTP connector instead of browser scraping",
    )
    parser.add_argument("--steam-login", action="store_true", help="Wait for manual Steam login")
    parser.add_argument("--steam-login-wait", type=int, default=120)
    parser.add_argument(
        "--steam-session-state",
        type=Path,
        default=Path("data/browser-state/steam_storage_state.json"),
    )
    parser.add_argument("--no-steam-session-state", action="store_true")
    parser.add_argument("--buff-login", action="store_true", help="Wait for manual BUFF login")
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
    parser.add_argument("--batch-size", type=int, default=runtime_config.workers.batch_size)
    parser.add_argument("--log-file", type=Path, help="Where to write detailed scraper logs")
    parser.add_argument("--persist", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    asyncio.run(run(args))


def build_simple_market_snapshots(
    candidates: tuple[SteamDTCandidate, ...],
    results: tuple[PlatformWorkerResult, ...],
    *,
    scraped_at: datetime,
) -> tuple[SimpleMarketSnapshot, ...]:
    candidates_by_hash = {
        candidate.market_hash_name: candidate
        for candidate in candidates
        if candidate.market_hash_name
    }
    strategies_by_hash: dict[str, list[dict[str, str | None]]] = {}
    for candidate in candidates:
        if not candidate.market_hash_name or not candidate.strategy_id:
            continue
        strategies_by_hash.setdefault(candidate.market_hash_name, []).append(
            {
                "strategy_id": candidate.strategy_id,
                "strategy_label": candidate.strategy_label,
                "balance_type": candidate.balance_type,
                "buy_mode": candidate.buy_mode,
                "sell_mode": candidate.sell_mode,
            }
        )
    grouped: dict[tuple[str, str, bool], dict[str, Any]] = {}

    for result in results:
        for record in result.observations:
            market_hash_name = str(record.observation.raw_payload.get("market_hash_name") or "")
            matched_candidate = candidates_by_hash.get(market_hash_name)
            name = _item_name(record, matched_candidate)
            quality = _quality(record, matched_candidate)
            if quality is None:
                continue
            stattrak = _stattrak(record, matched_candidate, market_hash_name)
            key = (name, quality, stattrak)
            entry = grouped.setdefault(
                key,
                {
                    "name": name,
                    "quality": quality,
                    "stattrak": stattrak,
                    "scraped_at": scraped_at,
                    "steam_url": (
                        matched_candidate.steam_url if matched_candidate else None
                    ),
                    "buff_url": matched_candidate.buff_url if matched_candidate else None,
                    "steam_price": None,
                    "steam_currency": None,
                    "steam_buy_orders": [],
                    "buff_price": None,
                    "buff_currency": None,
                    "buff_buy_orders": [],
                    "strategies": [],
                },
            )
            entry["strategies"].extend(strategies_by_hash.get(market_hash_name, ()))
            if matched_candidate:
                entry["steam_url"] = entry["steam_url"] or matched_candidate.steam_url
                entry["buff_url"] = entry["buff_url"] or matched_candidate.buff_url

            platform_id = record.observation.platform_id
            if platform_id == "steam":
                entry["steam_price"] = record.observation.price
                entry["steam_currency"] = record.observation.currency
                entry["steam_url"] = entry["steam_url"] or record.observation.source_reference
                entry["steam_buy_orders"] = record.observation.raw_payload.get("buy_orders") or []
            elif platform_id == "buff163":
                entry["buff_price"] = record.observation.price
                entry["buff_currency"] = record.observation.currency
                entry["buff_url"] = entry["buff_url"] or record.observation.source_reference
                entry["buff_buy_orders"] = record.observation.raw_payload.get("buy_orders") or []

    return tuple(
        SimpleMarketSnapshot(
            name=str(entry["name"]),
            quality=str(entry["quality"]),
            stattrak=bool(entry["stattrak"]),
            scraped_at=scraped_at,
            steam_url=_optional_str(entry.get("steam_url")),
            buff_url=_optional_str(entry.get("buff_url")),
            steam_price=entry.get("steam_price"),
            steam_currency=_optional_str(entry.get("steam_currency")),
            steam_buy_orders=tuple(_json_rows(entry.get("steam_buy_orders"))),
            buff_price=entry.get("buff_price"),
            buff_currency=_optional_str(entry.get("buff_currency")),
            buff_buy_orders=tuple(_json_rows(entry.get("buff_buy_orders"))),
            source_strategies=tuple(_unique_strategy_rows(entry.get("strategies"))),
        )
        for entry in grouped.values()
    )


def simple_results_to_jsonable(
    snapshots: tuple[SimpleMarketSnapshot, ...],
    results: tuple[PlatformWorkerResult, ...],
) -> dict[str, Any]:
    summary: dict[str, dict[str, int]] = {}
    for result in results:
        platform_summary = summary.setdefault(
            result.platform_id,
            {"observations": 0, "errors": 0},
        )
        platform_summary["observations"] += len(result.observations)
        platform_summary["errors"] += len(result.errors)

    return {
        "schema_version": "market_snapshot.v1",
        "items": [_snapshot_to_jsonable(snapshot) for snapshot in snapshots],
        "errors": [
            {
                "platform_id": error.platform_id,
                "market_hash_name": error.market_hash_name,
                "message": error.message,
            }
            for result in results
            for error in result.errors
        ],
        "summary": summary,
    }


async def _persist_snapshots(snapshots: tuple[SimpleMarketSnapshot, ...]) -> None:
    pool = await create_pool(max_size=2)
    try:
        async with pool.acquire() as connection:
            await SimpleMarketSnapshotRepository(connection).record_snapshots(snapshots)
    finally:
        await pool.close()


async def _save_login_states(args: argparse.Namespace, logger: logging.Logger) -> int:
    try:
        from playwright.async_api import async_playwright
    except ModuleNotFoundError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError("Playwright is required. Run: python -m pip install playwright") from exc

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=False)
        try:
            tasks = []
            if args.steam:
                tasks.append(
                    _login_platform(
                        browser,
                        name="steam",
                        url="https://steamcommunity.com/market/",
                        state_path=(
                            None
                            if args.no_steam_session_state
                            else args.steam_session_state
                        ),
                        wait_seconds=args.login_wait,
                        logger=logger,
                    )
                )
            if args.buff:
                tasks.append(
                    _login_platform(
                        browser,
                        name="buff163",
                        url="https://buff.163.com/market/csgo",
                        state_path=(
                            None
                            if args.no_buff_session_state
                            else args.buff_session_state
                        ),
                        wait_seconds=args.login_wait,
                        logger=logger,
                    )
                )
            if not tasks:
                print("login_only_platforms=none")
                logger.info("login_only_platforms=none")
                return 0
            await asyncio.gather(*tasks)
        finally:
            await browser.close()
    return 0


async def _login_platform(
    browser: Any,
    *,
    name: str,
    url: str,
    state_path: Path | None,
    wait_seconds: int,
    logger: logging.Logger,
) -> None:
    context_options: dict[str, Any] = {
        "viewport": {"width": 1920, "height": 1080},
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123 Safari/537.36"
        ),
    }
    if state_path is not None:
        state_exists = await asyncio.to_thread(state_path.exists)
        if state_exists:
            context_options["storage_state"] = str(state_path)
    context = await browser.new_context(**context_options)
    page = await context.new_page()
    try:
        print(f"{name}_login_url={url}")
        print(f"{name}_login_wait_seconds={wait_seconds}")
        logger.info("%s_login_url=%s", name, url)
        logger.info("%s_login_wait_seconds=%s", name, wait_seconds)
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(wait_seconds)
        if state_path:
            await asyncio.to_thread(state_path.parent.mkdir, parents=True, exist_ok=True)
            await context.storage_state(path=str(state_path))
            print(f"{name}_session_state_saved={state_path}")
            logger.info("%s_session_state_saved=%s", name, state_path)
        else:
            print(f"{name}_session_state_saved=disabled")
            logger.info("%s_session_state_saved=disabled", name)
    finally:
        await context.close()


def _default_output_path() -> Path:
    run_id = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S")
    return Path("data/flow-runs") / f"platform_observations_{run_id}.json"


def _chunks(
    candidates: tuple[SteamDTCandidate, ...],
    batch_size: int,
) -> tuple[tuple[SteamDTCandidate, ...], ...]:
    size = max(1, batch_size)
    return tuple(candidates[index : index + size] for index in range(0, len(candidates), size))


def _configure_logging(args: argparse.Namespace) -> tuple[logging.Logger, Path]:
    log_path = args.log_file or _default_log_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("csflipper.market_workers")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    return logger, log_path


def _default_log_path() -> Path:
    run_id = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S")
    return Path("logs") / f"market_workers_{run_id}.log"


def _item_name(record: Any, candidate: SteamDTCandidate | None) -> str:
    return _required_text(record.asset_name or (candidate.item_name if candidate else None), "name")


def _quality(record: Any, candidate: SteamDTCandidate | None) -> str | None:
    market_hash_name = str(record.observation.raw_payload.get("market_hash_name") or "")
    inferred_quality = quality_from_market_hash(
        market_hash_name or (candidate.market_hash_name if candidate else "")
    )
    return _optional_str(
        record.quality or (candidate.quality if candidate else None) or inferred_quality
    )


def _stattrak(
    record: Any,
    candidate: SteamDTCandidate | None,
    market_hash_name: str,
) -> bool:
    if candidate is not None:
        return candidate.stattrak
    text = f"{market_hash_name} {record.observation.asset_id}".lower()
    return "stattrak" in text


def _snapshot_to_jsonable(snapshot: SimpleMarketSnapshot) -> dict[str, Any]:
    return {
        "name": snapshot.name,
        "quality": snapshot.quality,
        "stattrak": snapshot.stattrak,
        "scraped_at": snapshot.scraped_at.isoformat(),
        "steam": _platform_snapshot_to_jsonable(
            url=snapshot.steam_url,
            price=snapshot.steam_price,
            currency=snapshot.steam_currency,
            recent_sales=snapshot.steam_recent_sales,
            buy_orders=snapshot.steam_buy_orders,
        ),
        "buff": _platform_snapshot_to_jsonable(
            url=snapshot.buff_url,
            price=snapshot.buff_price,
            currency=snapshot.buff_currency,
            recent_sales=snapshot.buff_recent_sales,
            buy_orders=snapshot.buff_buy_orders,
        ),
        **(
            {"source_strategies": list(snapshot.source_strategies)}
            if snapshot.source_strategies
            else {}
        ),
    }


def _platform_snapshot_to_jsonable(
    *,
    url: str | None,
    price: Any,
    currency: str | None,
    recent_sales: Sequence[Mapping[str, Any]],
    buy_orders: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if url:
        payload["url"] = url
    if price is not None:
        payload["price"] = str(price)
    if currency:
        payload["currency"] = currency
    if recent_sales:
        payload["recent_sales"] = list(recent_sales)
    if buy_orders:
        payload["buy_orders"] = list(buy_orders)
    return payload


def _print_batch_summary(
    batch_index: int,
    snapshot_count: int,
    results: tuple[PlatformWorkerResult, ...],
) -> None:
    parts = [
        f"{result.platform_id}={len(result.observations)} ok/{len(result.errors)} err"
        for result in results
    ]
    worker_summary = " | ".join(parts) if parts else "workers=disabled"
    print(f"batch {batch_index}: snapshots={snapshot_count} | {worker_summary}")


def _print_final_summary(
    *,
    output_path: Path,
    snapshots: int,
    summary: dict[str, dict[str, int]],
    persisted: bool,
) -> None:
    mode = "persisted" if persisted else "dry_run"
    print(f"done: snapshots={snapshots} mode={mode}")
    for platform_id, platform_summary in summary.items():
        print(
            f"  {platform_id}: "
            f"{platform_summary['observations']} observations, "
            f"{platform_summary['errors']} errors"
        )
    print(f"output_file={output_path}")


def _required_text(value: object, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"snapshot {field_name} cannot be empty")
    return text


def _optional_str(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _unique_strategy_rows(value: object) -> tuple[dict[str, str | None], ...]:
    if not isinstance(value, list):
        return ()
    seen: set[tuple[str | None, str | None, str | None, str | None, str | None]] = set()
    rows: list[dict[str, str | None]] = []
    for row in value:
        if not isinstance(row, dict):
            continue
        key = (
            _optional_str(row.get("strategy_id")),
            _optional_str(row.get("strategy_label")),
            _optional_str(row.get("balance_type")),
            _optional_str(row.get("buy_mode")),
            _optional_str(row.get("sell_mode")),
        )
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "strategy_id": key[0],
                "strategy_label": key[1],
                "balance_type": key[2],
                "buy_mode": key[3],
                "sell_mode": key[4],
            }
        )
    return tuple(rows)


def _json_rows(value: object) -> tuple[dict[str, Any], ...]:
    if not isinstance(value, list | tuple):
        return ()
    return tuple(dict(row) for row in value if isinstance(row, dict))


if __name__ == "__main__":
    main()

"""CLI command for scraping SteamDT candidates on Steam Market and BUFF."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
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
from apps.acquisition.steamdt_hanging import SteamDTCandidate
from packages.persistence.connection import create_pool
from packages.persistence.simple_market import (
    SimpleMarketSnapshot,
    SimpleMarketSnapshotRepository,
)


async def run(args: argparse.Namespace) -> int:
    logger, log_path = _configure_logging(args)
    print(f"market_workers_log_file={log_path}")
    if args.login_only:
        return await _save_login_states(args, logger)

    candidates_path = args.candidates or latest_steamdt_candidates_path(args.candidates_dir)
    print(f"steamdt_candidates_file={candidates_path}")
    logger.info("steamdt_candidates_file=%s", candidates_path)
    candidates = load_steamdt_candidates(candidates_path)
    logger.info("loaded_candidates=%s", len(candidates))
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
    results = await scrape_candidate_platforms(candidates, config=config, log=logger.info)
    snapshots = build_simple_market_snapshots(
        candidates,
        results,
        scraped_at=datetime.now(tz=UTC),
    )
    payload = simple_results_to_jsonable(snapshots, results)

    output_path = args.output or _default_output_path()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"platform_observations_file={output_path}")
    logger.info("platform_observations_file=%s", output_path)

    if args.persist and not args.dry_run:
        await _persist_snapshots(snapshots)
        print(f"imported_market_snapshots={len(snapshots)}")
    else:
        print(f"market_snapshots={len(snapshots)}")

    for platform_id, summary in payload["summary"].items():
        print(
            f"{platform_id}_worker="
            f"observations:{summary['observations']} errors:{summary['errors']}"
        )
        logger.info(
            "%s_worker=observations:%s errors:%s",
            platform_id,
            summary["observations"],
            summary["errors"],
        )
    for error in payload["errors"]:
        logger.error(
            "%s_error item=%s message=%s debug=%s",
            error["platform_id"],
            error["market_hash_name"],
            error["message"],
            " | ".join(error["debug_log"][-6:]),
        )
    return len(payload["observations"])


def main() -> None:
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
    parser.add_argument("--steam-concurrency", type=int, default=2)
    parser.add_argument("--buff-concurrency", type=int, default=1)
    parser.add_argument("--steam-min-delay", type=float, default=0.0)
    parser.add_argument("--steam-max-delay", type=float, default=0.0)
    parser.add_argument("--buff-min-delay", type=float, default=0.5)
    parser.add_argument("--buff-max-delay", type=float, default=2.0)
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
    grouped: dict[tuple[str, str, bool], dict[str, Any]] = {}

    for result in results:
        for record in result.observations:
            market_hash_name = str(record.observation.raw_payload.get("market_hash_name") or "")
            candidate = candidates_by_hash.get(market_hash_name)
            name = _item_name(record, candidate)
            quality = _quality(record, candidate)
            stattrak = _stattrak(record, candidate, market_hash_name)
            key = (name, quality, stattrak)
            entry = grouped.setdefault(
                key,
                {
                    "name": name,
                    "quality": quality,
                    "stattrak": stattrak,
                    "scraped_at": scraped_at,
                    "steam_url": candidate.steam_url if candidate else None,
                    "buff_url": candidate.buff_url if candidate else None,
                    "steam_price": None,
                    "steam_currency": None,
                    "buff_price": None,
                    "buff_currency": None,
                },
            )
            if candidate:
                entry["steam_url"] = entry["steam_url"] or candidate.steam_url
                entry["buff_url"] = entry["buff_url"] or candidate.buff_url

            platform_id = record.observation.platform_id
            if platform_id == "steam":
                entry["steam_price"] = record.observation.price
                entry["steam_currency"] = record.observation.currency
                entry["steam_url"] = entry["steam_url"] or record.observation.source_reference
            elif platform_id == "buff163":
                entry["buff_price"] = record.observation.price
                entry["buff_currency"] = record.observation.currency
                entry["buff_url"] = entry["buff_url"] or record.observation.source_reference

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
            buff_price=entry.get("buff_price"),
            buff_currency=_optional_str(entry.get("buff_currency")),
        )
        for entry in grouped.values()
    )


def simple_results_to_jsonable(
    snapshots: tuple[SimpleMarketSnapshot, ...],
    results: tuple[PlatformWorkerResult, ...],
) -> dict[str, Any]:
    return {
        "schema_version": "market_snapshot.v1",
        "items": [_snapshot_to_jsonable(snapshot) for snapshot in snapshots],
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

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    return logger, log_path


def _default_log_path() -> Path:
    run_id = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S")
    return Path("logs") / f"market_workers_{run_id}.log"


def _item_name(record: Any, candidate: SteamDTCandidate | None) -> str:
    return _required_text(record.asset_name or (candidate.item_name if candidate else None), "name")


def _quality(record: Any, candidate: SteamDTCandidate | None) -> str:
    return _required_text(record.quality or (candidate.quality if candidate else None), "quality")


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
        "steam": {
            "url": snapshot.steam_url,
            "price": str(snapshot.steam_price) if snapshot.steam_price is not None else None,
            "currency": snapshot.steam_currency,
            "recent_sales": list(snapshot.steam_recent_sales),
            "buy_orders": list(snapshot.steam_buy_orders),
        },
        "buff": {
            "url": snapshot.buff_url,
            "price": str(snapshot.buff_price) if snapshot.buff_price is not None else None,
            "currency": snapshot.buff_currency,
            "recent_sales": list(snapshot.buff_recent_sales),
            "buy_orders": list(snapshot.buff_buy_orders),
        },
    }


def _required_text(value: object, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"snapshot {field_name} cannot be empty")
    return text


def _optional_str(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


if __name__ == "__main__":
    main()

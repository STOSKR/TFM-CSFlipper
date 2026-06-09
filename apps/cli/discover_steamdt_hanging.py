"""CLI command for SteamDT Hanging candidate discovery."""

from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from apps.acquisition.steam_market import SteamMarketCandidate, SteamMarketConnector
from apps.acquisition.steamdt_hanging import (
    SteamDTCandidate,
    SteamDTHangingDiscovery,
    SteamDTHangingFilters,
    save_candidates,
)
from packages.persistence.connection import create_pool
from packages.persistence.repositories import MarketObservationIngestionRepository
from packages.runtime_config import load_runtime_config


@dataclass(frozen=True, slots=True)
class SteamDTProfile:
    balance_type: str
    sell_mode: str
    buy_mode: str | None
    min_price: Decimal | None = Decimal("300")
    max_price: Decimal | None = None
    min_volume: int | None = 12


PROFILES = {
    "steam_sell_slow": SteamDTProfile(
        balance_type="STEAM Balance",
        sell_mode="Sell at STEAM Lowest Price",
        buy_mode=None,
    ),
    "steam_sell_fast": SteamDTProfile(
        balance_type="STEAM Balance",
        sell_mode="Sell to STEAM Highest Buy Order",
        buy_mode=None,
    ),
    "platform_arbitrage_safe": SteamDTProfile(
        balance_type="Platform Balance",
        sell_mode="Sell at Platform Lowest Price",
        buy_mode="Buy via STEAM Buy Order",
    ),
    "platform_arbitrage_fast": SteamDTProfile(
        balance_type="Platform Balance",
        sell_mode="Sell to Platform Highest Buy Order",
        buy_mode="Buy at STEAM Lowest Price",
    ),
}


async def discover(args: argparse.Namespace) -> int:
    profile = PROFILES[args.profile]
    runtime_config = load_runtime_config()
    filters = SteamDTHangingFilters(
        headless=not args.show_browser,
        max_candidates=args.limit,
        min_price=(
            Decimal(str(args.min_price))
            if args.min_price is not None
            else runtime_config.discovery.min_price
        ),
        max_price=Decimal(str(args.max_price)) if args.max_price is not None else profile.max_price,
        min_volume=(
            args.min_volume
            if args.min_volume is not None
            else runtime_config.discovery.min_volume
        ),
        currency_code=args.currency,
        balance_type=args.balance_type or profile.balance_type,
        sell_mode=args.sell_mode or profile.sell_mode,
        buy_mode=args.buy_mode if args.buy_mode is not None else profile.buy_mode,
        platform_buff=args.platform_buff,
        platform_c5game=args.platform_c5game,
        platform_uu=args.platform_uu,
        enrich_missing_platform_links=args.enrich_links,
        steam_sale_fee_rate=Decimal(str(args.steam_fee_percent)) / Decimal("100"),
        withdrawal_fee_rate=Decimal(str(args.withdrawal_fee_percent)) / Decimal("100"),
        manual_login_wait_ms=args.login_wait * 1000 if args.login else 0,
        session_state_path=None if args.no_session_state else args.session_state,
    )
    candidates = await SteamDTHangingDiscovery(filters).discover()

    if args.output:
        save_candidates(args.output, candidates)
        print(f"steamdt_candidates_file={args.output}")

    if args.fetch_steam_prices:
        return await _fetch_steam_prices(candidates, persist=args.persist and not args.dry_run)

    if args.format == "json":
        for candidate in candidates:
            print(candidate.to_json())
    else:
        _print_candidates_table(
            candidates,
            Decimal(str(args.steam_fee_percent)),
            Decimal(str(args.withdrawal_fee_percent)),
        )
    print(f"steamdt_candidates={len(candidates)}")
    return len(candidates)


async def _fetch_steam_prices(
    candidates: tuple[SteamDTCandidate, ...],
    *,
    persist: bool,
) -> int:
    correlation_id = f"steamdt:{uuid4()}"
    async with SteamMarketConnector() as connector:
        observations = await connector.fetch_candidates(
            [
                SteamMarketCandidate(
                    market_hash_name=candidate.market_hash_name,
                    asset_name=candidate.item_name,
                    quality=candidate.quality,
                    stattrak=candidate.stattrak,
                )
                for candidate in candidates
            ],
            correlation_id=correlation_id,
        )

    if not persist:
        for observation in observations:
            print(observation.observation.model_dump_json())
        print(f"steam_price_observations={len(observations)}")
        return len(observations)

    pool = await create_pool(max_size=2)
    try:
        async with pool.acquire() as connection:
            repository = MarketObservationIngestionRepository(connection)
            for observation in observations:
                await repository.record_observation(
                    observation.observation,
                    asset_name=observation.asset_name,
                    category=observation.category,
                    quality=observation.quality,
                    variant_key=observation.variant_key,
                )
    finally:
        await pool.close()

    print(f"imported_steam_price_observations={len(observations)}")
    return len(observations)


def _print_candidates_table(
    candidates: tuple[SteamDTCandidate, ...],
    steam_fee_percent: Decimal,
    withdrawal_fee_percent: Decimal,
) -> None:
    if not candidates:
        print("No SteamDT candidates found.")
        return

    rows = [
        (
            str(index),
            _safe_console_text(candidate.item_name),
            candidate.quality or "",
            _money(candidate.buff_price, candidate.currency),
            _money(candidate.steam_price, candidate.currency),
            _money(candidate.break_even_steam_price, candidate.currency),
            _money(candidate.profit, candidate.currency),
            _percent(candidate.profitability_percent),
            _money(candidate.net_profit, candidate.currency),
            _percent(candidate.net_roi_percent),
            str(candidate.volume or ""),
        )
        for index, candidate in enumerate(candidates, start=1)
    ]
    headers = (
        "#",
        "Item",
        "Quality",
        "Buy",
        "Sell",
        "Break-even",
        "Gross P/L",
        "Gross ROI",
        "Net P/L",
        "Net ROI",
        "Vol",
    )
    widths = [
        min(max(len(row[column]) for row in (*rows, headers)), 48)
        for column in range(len(headers))
    ]
    print(_format_row(headers, widths))
    print(
        f"Fees: Steam {steam_fee_percent}% + withdrawal {withdrawal_fee_percent}%"
    )
    print(_format_row(tuple("-" * width for width in widths), widths))
    for row in rows:
        print(_format_row(row, widths))


def _format_row(values: tuple[str, ...], widths: list[int]) -> str:
    return "  ".join(
        value[: widths[index]].ljust(widths[index])
        for index, value in enumerate(values)
    )


def _money(value: Decimal | None, currency: str | None) -> str:
    if value is None:
        return ""
    suffix = f" {currency}" if currency else ""
    return f"{value.quantize(Decimal('0.01'))}{suffix}"


def _percent(value: Decimal | None) -> str:
    if value is None:
        return ""
    return f"{value.quantize(Decimal('0.01'))}%"


def _safe_console_text(value: str) -> str:
    encoding = sys.stdout.encoding or "utf-8"
    return value.encode(encoding, errors="replace").decode(encoding, errors="replace")


def main() -> None:
    runtime_config = load_runtime_config()
    parser = argparse.ArgumentParser(description="Discover candidates from SteamDT Hanging.")
    parser.add_argument(
        "--profile",
        choices=tuple(PROFILES),
        default="platform_arbitrage_safe",
    )
    parser.add_argument("--limit", type=int, default=runtime_config.discovery.candidates_limit)
    parser.add_argument("--min-price", type=float)
    parser.add_argument("--max-price", type=float)
    parser.add_argument("--min-volume", type=int)
    parser.add_argument("--currency", default=runtime_config.discovery.currency)
    parser.add_argument("--balance-type")
    parser.add_argument("--sell-mode")
    parser.add_argument("--buy-mode")
    parser.add_argument("--platform-buff", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--platform-c5game", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--platform-uu", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument(
        "--enrich-links",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Open SteamDT detail pages only when platform links are missing",
    )
    parser.add_argument("--show-browser", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--session-state",
        type=Path,
        default=Path("data/browser-state/steamdt_storage_state.json"),
        help="Playwright storage_state file for cookies and localStorage",
    )
    parser.add_argument("--no-session-state", action="store_true")
    parser.add_argument(
        "--login",
        action="store_true",
        help="Wait with the visible browser open so you can log in before scraping",
    )
    parser.add_argument(
        "--login-wait",
        type=int,
        default=120,
        help="Seconds to wait for manual login when --login is enabled",
    )
    parser.add_argument("--fetch-steam-prices", action="store_true")
    parser.add_argument(
        "--steam-fee-percent",
        type=float,
        default=float(runtime_config.fees.steam_sale_percent),
    )
    parser.add_argument(
        "--withdrawal-fee-percent",
        type=float,
        default=float(runtime_config.fees.withdrawal_percent),
    )
    parser.add_argument("--persist", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--format", choices=("table", "json"), default="table")
    args = parser.parse_args()

    asyncio.run(discover(args))


if __name__ == "__main__":
    main()

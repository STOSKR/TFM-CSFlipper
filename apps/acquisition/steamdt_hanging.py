"""SteamDT Hanging candidate discovery."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from apps.acquisition.steamdt_ui import (
    change_currency,
    click_confirm_search,
    click_tab_by_text,
    close_modal,
    configure_platforms,
    fill_price_volume_filters,
)
from packages.domain.market_parsing import (
    clean_text,
    detect_currency,
    market_hash_name,
    parse_int_from_text,
    parse_item_text,
    parse_market_decimal,
    parse_market_hash_from_steam_url,
)

STEAMDT_HANGING_URL = "https://www.steamdt.com/hanging"


class SteamDTDiscoveryError(RuntimeError):
    """Raised when SteamDT discovery cannot complete."""


@dataclass(frozen=True, slots=True)
class SteamDTHangingFilters:
    target_url: str = STEAMDT_HANGING_URL
    currency_code: str = "EUR"
    balance_type: str = "Platform Balance"
    sell_mode: str = "Sell at Platform Lowest Price"
    buy_mode: str | None = "Buy via STEAM Buy Order"
    min_price: Decimal | None = Decimal("100")
    max_price: Decimal | None = None
    min_volume: int | None = 12
    platform_buff: bool = True
    platform_c5game: bool = False
    platform_uu: bool = True
    headless: bool = True
    timeout_ms: int = 30000
    initial_wait_ms: int = 5000
    wait_after_search_ms: int = 3500
    max_candidates: int = 50


@dataclass(frozen=True, slots=True)
class SteamDTCandidate:
    item_name: str
    market_hash_name: str
    display_name: str | None = None
    quality: str | None = None
    stattrak: bool = False
    item_url: str | None = None
    buff_url: str | None = None
    steam_url: str | None = None
    currency: str | None = None
    buff_price: Decimal | None = None
    steam_price: Decimal | None = None
    profit: Decimal | None = None
    profitability_percent: Decimal | None = None
    volume: int | None = None
    raw_cells: tuple[str, ...] = ()

    def to_json(self) -> str:
        return json.dumps(asdict(self), default=str)


class SteamDTHangingDiscovery:
    """Playwright-powered discovery flow for SteamDT Hanging."""

    def __init__(self, filters: SteamDTHangingFilters | None = None) -> None:
        self.filters = filters or SteamDTHangingFilters()

    async def discover(self) -> tuple[SteamDTCandidate, ...]:
        try:
            from playwright.async_api import async_playwright
        except ModuleNotFoundError as exc:  # pragma: no cover - environment dependent
            raise SteamDTDiscoveryError(
                "Playwright is required. Run: python -m pip install playwright"
            ) from exc

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=self.filters.headless)
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123 Safari/537.36"
                ),
            )
            page = await context.new_page()
            try:
                await page.goto(
                    self.filters.target_url,
                    wait_until="domcontentloaded",
                    timeout=self.filters.timeout_ms,
                )
                await page.wait_for_selector(".tabs-item", timeout=self.filters.timeout_ms)
                await page.wait_for_timeout(self.filters.initial_wait_ms)
                await self._configure_filters(page)
                rows = await self._extract_rows(page)
            finally:
                await context.close()
                await browser.close()
        return parse_steamdt_rows(rows, limit=self.filters.max_candidates)

    async def _configure_filters(self, page: Any) -> None:
        await close_modal(page)
        await change_currency(page, self.filters.currency_code)
        await click_tab_by_text(page, self.filters.balance_type)
        await click_tab_by_text(page, self.filters.sell_mode)
        await click_tab_by_text(page, self.filters.buy_mode)
        await fill_price_volume_filters(
            page,
            min_price=self.filters.min_price,
            max_price=self.filters.max_price,
            min_volume=self.filters.min_volume,
        )
        await configure_platforms(
            page,
            platform_buff=self.filters.platform_buff,
            platform_c5game=self.filters.platform_c5game,
            platform_uu=self.filters.platform_uu,
        )
        await click_confirm_search(page)
        await page.wait_for_timeout(self.filters.wait_after_search_ms)

    async def _extract_rows(self, page: Any) -> list[dict[str, Any]]:
        rows = await page.evaluate(
            """
            () => Array.from(document.querySelectorAll('.el-table__body .el-table__row'))
              .map((row) => ({
                cells: Array.from(row.querySelectorAll('td')).map((td) => td.innerText),
                links: Array.from(row.querySelectorAll('a')).map((a) => a.href)
              }))
            """
        )
        if not rows:
            rows = await page.evaluate(
                """
                () => Array.from(document.querySelectorAll('tr'))
                  .map((row) => ({
                    cells: Array.from(row.querySelectorAll('td')).map((td) => td.innerText),
                    links: Array.from(row.querySelectorAll('a')).map((a) => a.href)
                  }))
                """
            )
        return list(rows)


def parse_steamdt_rows(
    rows: list[dict[str, Any]],
    *,
    limit: int | None = None,
) -> tuple[SteamDTCandidate, ...]:
    candidates: list[SteamDTCandidate] = []
    for row in rows:
        candidate = parse_steamdt_row(row)
        if candidate is None:
            continue
        candidates.append(candidate)
        if limit is not None and len(candidates) >= limit:
            break
    return tuple(candidates)


def parse_steamdt_row(row: dict[str, Any]) -> SteamDTCandidate | None:
    cells = tuple(clean_text(value) for value in row.get("cells", ()))
    links = tuple(str(value) for value in row.get("links", ()))
    if len(cells) < 4:
        return None

    display_name, display_quality, display_stattrak = parse_item_text(cells[1])
    buff_url = _find_url(links, "buff.163.com")
    steam_url = _find_url(links, "steamcommunity.com/market/listings")
    steam_market_hash = parse_market_hash_from_steam_url(steam_url)

    if steam_market_hash:
        item_name, quality, stattrak = parse_item_text(steam_market_hash)
        candidate_market_hash = steam_market_hash
    else:
        item_name = display_name
        quality = display_quality
        stattrak = display_stattrak
        candidate_market_hash = market_hash_name(item_name, quality)

    if _should_skip_item(item_name):
        return None

    return SteamDTCandidate(
        item_name=item_name,
        market_hash_name=candidate_market_hash,
        display_name=display_name if display_name != item_name else None,
        quality=quality,
        stattrak=stattrak,
        item_url=_find_url(links, "steamdt.com") or _find_url(links, "/item/"),
        buff_url=buff_url,
        steam_url=steam_url,
        currency=detect_currency(" ".join(cells[2:5])),
        buff_price=parse_market_decimal(cells[2]) if len(cells) > 2 else None,
        steam_price=parse_market_decimal(cells[3]) if len(cells) > 3 else None,
        profit=parse_market_decimal(cells[4]) if len(cells) > 4 else None,
        profitability_percent=parse_market_decimal(cells[6]) if len(cells) > 6 else None,
        volume=parse_int_from_text(cells[5]) if len(cells) > 5 else None,
        raw_cells=cells,
    )


def _should_skip_item(item_name: str) -> bool:
    lowered = item_name.lower()
    return (
        "|" not in item_name
        or lowered.startswith("sticker")
        or lowered.startswith("charm |")
        or lowered.startswith("patch |")
        or "music kit" in lowered
    )


def _find_url(links: tuple[str, ...], pattern: str) -> str | None:
    for link in links:
        if pattern in link:
            return link
    return None


def save_candidates(path: str | Path, candidates: tuple[SteamDTCandidate, ...]) -> None:
    Path(path).write_text(
        json.dumps([asdict(candidate) for candidate in candidates], default=str, indent=2),
        encoding="utf-8",
    )

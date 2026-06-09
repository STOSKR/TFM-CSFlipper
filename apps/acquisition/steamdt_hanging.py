"""SteamDT Hanging candidate discovery."""

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, dataclass, replace
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

STEAMDT_HANGING_URL = "https://www.steamdt.com/en/hanging"


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
    wait_after_detail_ms: int = 1200
    manual_login_wait_ms: int = 0
    max_candidates: int = 50
    enrich_missing_platform_links: bool = False
    max_detail_concurrency: int = 2
    steam_sale_fee_rate: Decimal = Decimal("0.13")
    withdrawal_fee_rate: Decimal = Decimal("0.20")
    session_state_path: Path | None = Path("data/browser-state/steamdt_storage_state.json")


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
    net_profit: Decimal | None = None
    net_roi_percent: Decimal | None = None
    break_even_steam_price: Decimal | None = None
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
            context_options: dict[str, Any] = {
                "viewport": {"width": 1920, "height": 1080},
                "user_agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123 Safari/537.36"
                ),
            }
            if self.filters.session_state_path and self.filters.session_state_path.exists():
                context_options["storage_state"] = str(self.filters.session_state_path)
            context = await browser.new_context(**context_options)
            page = await context.new_page()
            try:
                await page.goto(
                    self.filters.target_url,
                    wait_until="domcontentloaded",
                    timeout=self.filters.timeout_ms,
                )
                await close_modal(page)
                if self.filters.manual_login_wait_ms > 0:
                    await page.wait_for_timeout(self.filters.manual_login_wait_ms)
                await page.wait_for_selector(".tabs-item", timeout=self.filters.timeout_ms)
                await page.wait_for_timeout(self.filters.initial_wait_ms)
                await self._configure_filters(page)
                rows = await self._extract_rows(page)
                candidates = parse_steamdt_rows(
                    rows,
                    limit=self.filters.max_candidates,
                    steam_sale_fee_rate=self.filters.steam_sale_fee_rate,
                    withdrawal_fee_rate=self.filters.withdrawal_fee_rate,
                )
                candidates = await self._enrich_missing_platform_links(context, candidates)
            finally:
                await self._save_session_state(context)
                await context.close()
                await browser.close()
        return candidates

    async def _save_session_state(self, context: Any) -> None:
        if not self.filters.session_state_path:
            return
        self.filters.session_state_path.parent.mkdir(parents=True, exist_ok=True)
        await context.storage_state(path=str(self.filters.session_state_path))

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

    async def _enrich_missing_platform_links(
        self,
        context: Any,
        candidates: tuple[SteamDTCandidate, ...],
    ) -> tuple[SteamDTCandidate, ...]:
        if not self.filters.enrich_missing_platform_links:
            return candidates

        async def enrich_one(candidate: SteamDTCandidate) -> SteamDTCandidate:
            if candidate.buff_url or not candidate.item_url:
                return candidate
            page = await context.new_page()
            try:
                await page.goto(
                    candidate.item_url,
                    wait_until="domcontentloaded",
                    timeout=self.filters.timeout_ms,
                )
                await page.wait_for_timeout(self.filters.wait_after_detail_ms)
                links = await page.evaluate(
                    """
                    () => Array.from(document.querySelectorAll('a')).map((a) => a.href)
                    """
                )
                return merge_candidate_links(candidate, tuple(str(link) for link in links))
            except Exception:
                return candidate
            finally:
                await page.close()

        semaphore = asyncio.Semaphore(self.filters.max_detail_concurrency)

        async def limited_enrich(candidate: SteamDTCandidate) -> SteamDTCandidate:
            async with semaphore:
                return await enrich_one(candidate)

        return tuple(await asyncio.gather(*(limited_enrich(c) for c in candidates)))


def parse_steamdt_rows(
    rows: list[dict[str, Any]],
    *,
    limit: int | None = None,
    steam_sale_fee_rate: Decimal = Decimal("0.13"),
    withdrawal_fee_rate: Decimal = Decimal("0.20"),
) -> tuple[SteamDTCandidate, ...]:
    candidates: list[SteamDTCandidate] = []
    for row in rows:
        candidate = parse_steamdt_row(
            row,
            steam_sale_fee_rate=steam_sale_fee_rate,
            withdrawal_fee_rate=withdrawal_fee_rate,
        )
        if candidate is None:
            continue
        candidates.append(candidate)
        if limit is not None and len(candidates) >= limit:
            break
    return tuple(candidates)


def parse_steamdt_row(
    row: dict[str, Any],
    *,
    steam_sale_fee_rate: Decimal = Decimal("0.13"),
    withdrawal_fee_rate: Decimal = Decimal("0.20"),
) -> SteamDTCandidate | None:
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

    buy_price = parse_market_decimal(cells[2]) if len(cells) > 2 else None
    sell_price = parse_market_decimal(cells[3]) if len(cells) > 3 else None

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
        buff_price=buy_price,
        steam_price=sell_price,
        profit=calculate_gross_profit(buy_price, sell_price),
        profitability_percent=calculate_gross_roi_percent(buy_price, sell_price),
        net_profit=calculate_net_profit(
            buy_price,
            sell_price,
            steam_sale_fee_rate=steam_sale_fee_rate,
            withdrawal_fee_rate=withdrawal_fee_rate,
        ),
        net_roi_percent=calculate_net_roi_percent(
            buy_price,
            sell_price,
            steam_sale_fee_rate=steam_sale_fee_rate,
            withdrawal_fee_rate=withdrawal_fee_rate,
        ),
        break_even_steam_price=calculate_break_even_steam_price(
            buy_price,
            steam_sale_fee_rate=steam_sale_fee_rate,
            withdrawal_fee_rate=withdrawal_fee_rate,
        ),
        volume=parse_int_from_text(cells[5]) if len(cells) > 5 else None,
        raw_cells=cells,
    )


def calculate_gross_profit(
    buy_price: Decimal | None,
    sell_price: Decimal | None,
) -> Decimal | None:
    if buy_price is None or sell_price is None:
        return None
    return sell_price - buy_price


def calculate_gross_roi_percent(
    buy_price: Decimal | None,
    sell_price: Decimal | None,
) -> Decimal | None:
    profit = calculate_gross_profit(buy_price, sell_price)
    if profit is None or buy_price is None or buy_price == 0:
        return None
    return (profit / buy_price) * Decimal("100")


def calculate_net_received(
    sell_price: Decimal | None,
    *,
    steam_sale_fee_rate: Decimal,
    withdrawal_fee_rate: Decimal,
) -> Decimal | None:
    if sell_price is None:
        return None
    return sell_price * _net_multiplier(
        steam_sale_fee_rate=steam_sale_fee_rate,
        withdrawal_fee_rate=withdrawal_fee_rate,
    )


def calculate_net_profit(
    buy_price: Decimal | None,
    sell_price: Decimal | None,
    *,
    steam_sale_fee_rate: Decimal,
    withdrawal_fee_rate: Decimal,
) -> Decimal | None:
    net_received = calculate_net_received(
        sell_price,
        steam_sale_fee_rate=steam_sale_fee_rate,
        withdrawal_fee_rate=withdrawal_fee_rate,
    )
    if buy_price is None or net_received is None:
        return None
    return net_received - buy_price


def calculate_net_roi_percent(
    buy_price: Decimal | None,
    sell_price: Decimal | None,
    *,
    steam_sale_fee_rate: Decimal,
    withdrawal_fee_rate: Decimal,
) -> Decimal | None:
    net_profit = calculate_net_profit(
        buy_price,
        sell_price,
        steam_sale_fee_rate=steam_sale_fee_rate,
        withdrawal_fee_rate=withdrawal_fee_rate,
    )
    if buy_price is None or buy_price == 0 or net_profit is None:
        return None
    return (net_profit / buy_price) * Decimal("100")


def calculate_break_even_steam_price(
    buy_price: Decimal | None,
    *,
    steam_sale_fee_rate: Decimal,
    withdrawal_fee_rate: Decimal,
) -> Decimal | None:
    if buy_price is None:
        return None
    multiplier = _net_multiplier(
        steam_sale_fee_rate=steam_sale_fee_rate,
        withdrawal_fee_rate=withdrawal_fee_rate,
    )
    if multiplier <= 0:
        return None
    return buy_price / multiplier


def _net_multiplier(
    *,
    steam_sale_fee_rate: Decimal,
    withdrawal_fee_rate: Decimal,
) -> Decimal:
    return (Decimal("1") - steam_sale_fee_rate) * (Decimal("1") - withdrawal_fee_rate)


def merge_candidate_links(
    candidate: SteamDTCandidate,
    links: tuple[str, ...],
) -> SteamDTCandidate:
    """Fill missing platform links from a SteamDT detail page."""

    buff_url = candidate.buff_url or _find_url(links, "buff.163.com")
    steam_url = candidate.steam_url or _find_url(links, "steamcommunity.com/market/listings")
    item_url = candidate.item_url or _find_url(links, "steamdt.com") or _find_url(links, "/item/")
    if (
        buff_url == candidate.buff_url
        and steam_url == candidate.steam_url
        and item_url == candidate.item_url
    ):
        return candidate
    return replace(candidate, buff_url=buff_url, steam_url=steam_url, item_url=item_url)


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
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps([asdict(candidate) for candidate in candidates], default=str, indent=2),
        encoding="utf-8",
    )

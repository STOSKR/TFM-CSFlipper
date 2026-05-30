"""SteamDT Hanging candidate discovery."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

STEAMDT_HANGING_URL = "https://www.steamdt.com/hanging"
QUALITY_PATTERN = re.compile(
    r"\((Factory New|Minimal Wear|Field-Tested|Well-Worn|Battle-Scarred)\)\s*$",
    re.IGNORECASE,
)


class SteamDTDiscoveryError(RuntimeError):
    """Raised when SteamDT discovery cannot complete."""


@dataclass(frozen=True, slots=True)
class SteamDTHangingFilters:
    target_url: str = STEAMDT_HANGING_URL
    currency_code: str = "EUR"
    balance_type: str = "Platform Balance"
    sell_mode: str = "Sell at Platform Lowest Price"
    buy_mode: str | None = "Buy via STEAM Buy Order"
    min_price: Decimal | None = Decimal("300")
    max_price: Decimal | None = None
    min_volume: int | None = 12
    platform_buff: bool = True
    platform_c5game: bool = False
    platform_uu: bool = False
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
        await _close_modal(page)
        await _change_currency(page, self.filters.currency_code)
        await _click_tab_by_text(page, self.filters.balance_type)
        await _click_tab_by_text(page, self.filters.sell_mode)
        if self.filters.buy_mode:
            await _click_tab_by_text(page, self.filters.buy_mode)
        await _fill_price_volume_filters(page, self.filters)
        await _configure_platforms(page, self.filters)
        await _click_confirm_search(page)
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
    cells = tuple(_clean_text(value) for value in row.get("cells", ()))
    links = tuple(str(value) for value in row.get("links", ()))
    if len(cells) < 4:
        return None

    item_text = cells[1]
    display_name, display_quality, display_stattrak = _parse_item_text(item_text)
    buff_url = _find_url(links, "buff.163.com")
    steam_url = _find_url(links, "steamcommunity.com/market/listings")
    steam_market_hash = _market_hash_from_steam_url(steam_url)

    if steam_market_hash:
        item_name, quality, stattrak = _parse_item_text(steam_market_hash)
        market_hash_name = steam_market_hash
    else:
        item_name = display_name
        quality = display_quality
        stattrak = display_stattrak
        market_hash_name = _market_hash_name(item_name, quality)

    if _should_skip_item(item_name):
        return None

    item_url = _find_url(links, "steamdt.com") or _find_url(links, "/item/")
    currency = _detect_currency(" ".join(cells[2:5]))

    return SteamDTCandidate(
        item_name=item_name,
        market_hash_name=market_hash_name,
        display_name=display_name if display_name != item_name else None,
        quality=quality,
        stattrak=stattrak,
        item_url=item_url,
        buff_url=buff_url,
        steam_url=steam_url,
        currency=currency,
        buff_price=_parse_decimal_from_text(cells[2]) if len(cells) > 2 else None,
        steam_price=_parse_decimal_from_text(cells[3]) if len(cells) > 3 else None,
        profit=_parse_decimal_from_text(cells[4]) if len(cells) > 4 else None,
        profitability_percent=_parse_decimal_from_text(cells[6]) if len(cells) > 6 else None,
        volume=_parse_int_from_text(cells[5]) if len(cells) > 5 else None,
        raw_cells=cells,
    )


async def _close_modal(page: Any) -> None:
    close_selectors = (
        ".el-dialog__headerbtn",
        'button[aria-label="Close"]',
        'button:has-text("我已知晓")',
        'button:has-text("我知道了")',
        'button:has-text("同意")',
        'button:has-text("I understand")',
        'button:has-text("OK")',
        ".el-overlay-dialog .el-button",
    )
    for _ in range(3):
        clicked = False
        for selector in close_selectors:
            elements = await page.locator(selector).all()
            for element in elements:
                if await element.is_visible():
                    await element.click(force=True)
                    await page.wait_for_timeout(700)
                    clicked = True
        if not clicked:
            return


async def _change_currency(page: Any, currency_code: str) -> None:
    if not currency_code:
        return
    for selector in (".el-dropdown-link", "[class*='currency']", "[class*='dropdown']"):
        locator = page.locator(selector)
        if await locator.count() == 0:
            continue
        await locator.first.click(force=True)
        await page.wait_for_timeout(500)
        option = page.locator(f'li:has-text("{currency_code}")')
        if await option.count() > 0:
            await option.first.click(force=True)
            await page.wait_for_timeout(1500)
            return
        await page.keyboard.press("Escape")


async def _click_tab_by_text(page: Any, text: str) -> None:
    if not text:
        return
    labels = _localized_tab_labels(text)
    locator = page.locator(f'.tabs-item:has-text("{labels[0]}")')
    if await locator.count() == 0:
        for label in labels[1:]:
            locator = page.locator(f'.tabs-item:has-text("{label}")')
            if await locator.count() > 0:
                break
    if await locator.count() == 0:
        for label in labels:
            locator = page.locator(f'text="{label}"')
            if await locator.count() > 0:
                break
    if await locator.count() == 0:
        return
    target = locator.first
    class_name = await target.get_attribute("class") or ""
    if "active" not in class_name:
        await target.click(force=True)
        await page.wait_for_timeout(500)


def _localized_tab_labels(text: str) -> tuple[str, ...]:
    labels = {
        "STEAM Balance": ("STEAM Balance", "STEAM余额"),
        "Platform Balance": ("Platform Balance", "平台余额"),
        "Sell at STEAM Lowest Price": ("Sell at STEAM Lowest Price", "STEAM挂底价"),
        "Sell to STEAM Highest Buy Order": (
            "Sell to STEAM Highest Buy Order",
            "STEAM丢求购",
        ),
        "Sell at Platform Lowest Price": ("Sell at Platform Lowest Price", "平台挂底价"),
        "Sell to Platform Highest Buy Order": (
            "Sell to Platform Highest Buy Order",
            "平台丢求购",
        ),
        "Buy via STEAM Buy Order": ("Buy via STEAM Buy Order", "STEAM求购"),
        "Buy at STEAM Lowest Price": ("Buy at STEAM Lowest Price", "STEAM底价"),
    }
    return labels.get(text, (text,))


async def _fill_price_volume_filters(page: Any, filters: SteamDTHangingFilters) -> None:
    inputs = await page.locator(".el-input__inner:not(#searchInput)").all()
    values = [filters.min_price, filters.max_price, filters.min_volume]
    for index, value in enumerate(values):
        if value is None or index >= len(inputs):
            continue
        await inputs[index].fill(str(value), force=True)
        await page.wait_for_timeout(150)


async def _configure_platforms(page: Any, filters: SteamDTHangingFilters) -> None:
    settings = page.locator('.text-blue:has-text("Platform Settings")')
    if await settings.count() > 0:
        await settings.first.click()
        await page.wait_for_timeout(500)
    for label, enabled in (
        ("C5GAME", filters.platform_c5game),
        ("UU", filters.platform_uu),
        ("BUFF", filters.platform_buff),
    ):
        checkbox = page.locator(f'.el-checkbox:has-text("{label}")')
        if await checkbox.count() == 0:
            continue
        input_box = checkbox.first.locator('input[type="checkbox"]')
        if await input_box.count() == 0:
            continue
        checked = await input_box.first.is_checked()
        if checked != enabled:
            await checkbox.first.click(force=True)
            await page.wait_for_timeout(150)


async def _click_confirm_search(page: Any) -> None:
    for selector in (
        '.bg-\\[\\#0252D9\\]:has-text("Confirm and Search")',
        'button:has-text("Confirm and Search")',
        'button:has-text("Search")',
        'text="确定并搜索"',
    ):
        locator = page.locator(selector)
        if await locator.count() > 0:
            await locator.first.click(force=True)
            return


def _parse_item_text(value: str) -> tuple[str, str | None, bool]:
    text = _clean_text(value)
    stattrak = "stattrak" in text.lower()
    match = QUALITY_PATTERN.search(text)
    quality = match.group(1) if match else None
    if quality:
        text = QUALITY_PATTERN.sub("", text).strip()
    return text, quality, stattrak


def _should_skip_item(item_name: str) -> bool:
    lowered = item_name.lower()
    return (
        "|" not in item_name
        or lowered.startswith("sticker")
        or lowered.startswith("charm |")
        or lowered.startswith("patch |")
        or "music kit" in lowered
    )


def _market_hash_name(item_name: str, quality: str | None) -> str:
    return f"{item_name} ({quality})" if quality else item_name


def _market_hash_from_steam_url(url: str | None) -> str | None:
    if not url:
        return None
    path = urlparse(url).path
    parts = path.split("/market/listings/730/")
    if len(parts) != 2:
        return None
    return unquote(parts[1])


def _find_url(links: tuple[str, ...], pattern: str) -> str | None:
    for link in links:
        if pattern in link:
            return link
    return None


def _parse_decimal_from_text(value: str) -> Decimal | None:
    match = re.search(r"\d[\d.,]*", value)
    if match is None:
        return None
    cleaned = match.group(0)
    if "," in cleaned and "." in cleaned:
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif "," in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    try:
        return Decimal(cleaned)
    except Exception:
        return None


def _detect_currency(value: str) -> str | None:
    lowered = value.lower()
    if "eur" in lowered or "€" in value:
        return "EUR"
    if "¥" in value or "cny" in lowered:
        return "CNY"
    if "$" in value or "usd" in lowered:
        return "USD"
    if "£" in value or "gbp" in lowered:
        return "GBP"
    return None


def _parse_int_from_text(value: str) -> int | None:
    digits = re.sub(r"[^0-9]", "", value)
    return int(digits) if digits else None


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def save_candidates(path: str | Path, candidates: tuple[SteamDTCandidate, ...]) -> None:
    Path(path).write_text(
        json.dumps([asdict(candidate) for candidate in candidates], default=str, indent=2),
        encoding="utf-8",
    )

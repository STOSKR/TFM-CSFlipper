"""SteamDT Hanging candidate discovery."""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Awaitable, Callable
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
    current_option_description,
    fill_price_volume_filters,
    try_click_tab_by_text,
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
HEADLESS_CHROMIUM_ARGS = (
    "--disable-background-networking",
    "--disable-default-apps",
    "--disable-dev-shm-usage",
    "--disable-extensions",
    "--disable-gpu",
    "--disable-renderer-backgrounding",
    "--disable-setuid-sandbox",
    "--mute-audio",
    "--no-default-browser-check",
    "--no-first-run",
    "--no-sandbox",
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
    min_price: Decimal | None = Decimal("100")
    max_price: Decimal | None = None
    min_volume: int | None = 12
    platform_buff: bool = True
    platform_c5game: bool = False
    platform_uu: bool = False
    headless: bool = True
    timeout_ms: int = 60000
    navigation_retries: int = 2
    initial_wait_ms: int = 5000
    wait_after_search_ms: int = 3500
    wait_after_detail_ms: int = 1200
    manual_login_wait_ms: int = 0
    max_candidates: int = 50
    enrich_missing_platform_links: bool = False
    max_detail_concurrency: int = 2
    block_heavy_resources: bool = True
    browser_args: tuple[str, ...] = HEADLESS_CHROMIUM_ARGS
    steam_sale_fee_rate: Decimal = Decimal("0.13")
    withdrawal_fee_rate: Decimal = Decimal("0.20")
    session_state_path: Path | None = Path("data/browser-state/steamdt_storage_state.json")


@dataclass(frozen=True, slots=True)
class SteamDTCandidate:
    item_name: str
    market_hash_name: str
    strategy_id: str | None = None
    strategy_label: str | None = None
    balance_type: str | None = None
    buy_mode: str | None = None
    sell_mode: str | None = None
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

    def __init__(
        self,
        filters: SteamDTHangingFilters | None = None,
        *,
        progress_log: Callable[[str], None] | None = None,
    ) -> None:
        self.filters = filters or SteamDTHangingFilters()
        self._progress_log = progress_log

    async def discover(self) -> tuple[SteamDTCandidate, ...]:
        try:
            from playwright.async_api import TimeoutError as PlaywrightTimeoutError
            from playwright.async_api import async_playwright
        except ModuleNotFoundError as exc:  # pragma: no cover - environment dependent
            raise SteamDTDiscoveryError(
                "Playwright is required. Run: python -m pip install playwright"
            ) from exc

        async with async_playwright() as playwright:
            self._log("steamdt_stage=launch_browser")
            browser = await playwright.chromium.launch(
                headless=self.filters.headless,
                args=list(self.filters.browser_args) if self.filters.headless else None,
            )
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
            page.set_default_timeout(min(self.filters.timeout_ms, 10_000))
            candidates: tuple[SteamDTCandidate, ...] = ()
            try:
                if self.filters.block_heavy_resources:
                    await self._block_heavy_resources(page)
                self._log("steamdt_stage=goto")
                await self._goto_target(page, PlaywrightTimeoutError)
                self._log("steamdt_stage=close_modal")
                await close_modal(page)
                self._log("steamdt_stage=modal_closed")
                if self.filters.manual_login_wait_ms > 0:
                    self._log("steamdt_stage=manual_login_wait")
                    await page.wait_for_timeout(self.filters.manual_login_wait_ms)
                self._log("steamdt_stage=wait_tabs")
                try:
                    await page.wait_for_selector(".tabs-item", timeout=self.filters.timeout_ms)
                except PlaywrightTimeoutError:
                    self._log("steamdt_stage=wait_tabs status=timeout_continue")
                    await self._log_page_state_bounded(page, "wait_tabs")
                else:
                    self._log("steamdt_stage=wait_tabs status=ok")
                await page.wait_for_timeout(self.filters.initial_wait_ms)
                self._log("steamdt_stage=configure_filters")
                configured = await self._configure_filters(page)
                if not configured:
                    self._log("steamdt_stage=done count=0 reason=configure_failed")
                    return ()
                self._log("steamdt_stage=extract_rows")
                rows = await self._extract_rows(page)
                self._log(f"steamdt_stage=parse_rows rows={len(rows)}")
                candidates = parse_steamdt_rows(
                    rows,
                    limit=self.filters.max_candidates,
                    steam_sale_fee_rate=self.filters.steam_sale_fee_rate,
                    withdrawal_fee_rate=self.filters.withdrawal_fee_rate,
                )
                self._log(f"steamdt_stage=parsed_candidates count={len(candidates)}")
                candidates = await self._enrich_missing_platform_links(context, candidates)
                self._log(f"steamdt_stage=done count={len(candidates)}")
            finally:
                await self._run_cleanup_step(
                    "save_session_state",
                    self._save_session_state(context),
                )
                await self._run_cleanup_step("context_close", context.close())
                await self._run_cleanup_step("browser_close", browser.close())
        return candidates

    def _log(self, message: str) -> None:
        if self._progress_log is not None:
            self._progress_log(message)

    async def _block_heavy_resources(self, page: Any) -> None:
        async def route_handler(route: Any) -> None:
            if route.request.resource_type in {"font", "image", "media"}:
                await route.abort()
                return
            await route.continue_()

        await page.route("**/*", route_handler)

    async def _goto_target(
        self,
        page: Any,
        timeout_error_type: type[Exception],
    ) -> None:
        attempts = max(1, self.filters.navigation_retries + 1)
        for attempt_index in range(attempts):
            try:
                await page.goto(
                    self.filters.target_url,
                    wait_until="domcontentloaded",
                    timeout=self.filters.timeout_ms,
                )
                return
            except timeout_error_type:
                if attempt_index == attempts - 1:
                    raise
                await page.wait_for_timeout(min(1000 * (attempt_index + 1), 5000))

    async def _save_session_state(self, context: Any) -> None:
        if not self.filters.session_state_path:
            return
        self.filters.session_state_path.parent.mkdir(parents=True, exist_ok=True)
        await context.storage_state(path=str(self.filters.session_state_path))

    async def _configure_filters(self, page: Any) -> bool:
        steps: tuple[tuple[str, Callable[[], Awaitable[object]]], ...] = (
            ("currency", lambda: change_currency(page, self.filters.currency_code)),
            ("balance", lambda: click_tab_by_text(page, self.filters.balance_type)),
            ("buy_mode", lambda: try_click_tab_by_text(page, self.filters.buy_mode)),
            ("sell_mode", lambda: click_tab_by_text(page, self.filters.sell_mode)),
            (
                "filters",
                lambda: fill_price_volume_filters(
                    page,
                    min_price=self.filters.min_price,
                    max_price=self.filters.max_price,
                    min_volume=self.filters.min_volume,
                ),
            ),
            (
                "platforms",
                lambda: configure_platforms(
                    page,
                    platform_buff=self.filters.platform_buff,
                    platform_c5game=self.filters.platform_c5game,
                    platform_uu=self.filters.platform_uu,
                ),
            ),
            ("confirm_search", lambda: click_confirm_search(page)),
        )
        for name, action_factory in steps:
            status = await self._run_ui_step(page, name, action_factory())
            if status != "ok":
                self._log(
                    f"steamdt_stage=configure_filters status=aborted_after step={name}"
                )
                return False
        description = await current_option_description(page)
        self._log(
            "steamdt_selected_options "
            f"balance={_compact_debug_text(self.filters.balance_type)} "
            f"buy={_compact_debug_text(self.filters.buy_mode or '-')} "
            f"sell={_compact_debug_text(self.filters.sell_mode)} "
            f"description={_compact_debug_text(description, max_length=260)}"
        )
        await page.wait_for_timeout(self.filters.wait_after_search_ms)
        return True

    async def _run_ui_step(
        self,
        page: Any,
        name: str,
        action: Awaitable[object],
        *,
        timeout_seconds: float = 8.0,
    ) -> str:
        self._log(f"steamdt_stage=configure.{name}")
        try:
            await asyncio.wait_for(action, timeout=timeout_seconds)
        except TimeoutError:
            self._log(f"steamdt_stage=configure.{name} status=timeout")
            await self._log_page_state_bounded(page, name)
            return "timeout"
        except Exception as exc:
            self._log(
                f"steamdt_stage=configure.{name} status=error error={type(exc).__name__}"
            )
            await self._log_page_state_bounded(page, name)
            return "error"
        else:
            self._log(f"steamdt_stage=configure.{name} status=ok")
            return "ok"

    async def _log_page_state_bounded(self, page: Any, step_name: str) -> None:
        try:
            await asyncio.wait_for(self._log_page_state(page, step_name), timeout=3.0)
        except TimeoutError:
            self._log(f"steamdt_debug step={step_name} status=debug_timeout")
        except Exception as exc:
            self._log(
                f"steamdt_debug step={step_name} status=debug_error "
                f"error={type(exc).__name__}"
            )

    async def _run_cleanup_step(
        self,
        name: str,
        action: Awaitable[object],
        *,
        timeout_seconds: float = 3.0,
    ) -> None:
        try:
            await asyncio.wait_for(action, timeout=timeout_seconds)
        except TimeoutError:
            self._log(f"steamdt_cleanup={name} status=timeout")
        except Exception as exc:
            self._log(f"steamdt_cleanup={name} status=error error={type(exc).__name__}")
        else:
            self._log(f"steamdt_cleanup={name} status=ok")

    async def _log_page_state(self, page: Any, step_name: str) -> None:
        try:
            title = await page.title()
        except Exception:
            title = "<unavailable>"
        try:
            state = await page.evaluate(
                """
                () => {
                  const clean = (value) => String(value || '')
                    .replace(/\\s+/g, ' ')
                    .trim();
                  return {
                    url: location.href,
                    tabs: document.querySelectorAll('.tabs-item').length,
                    inputs: document.querySelectorAll('.el-input__inner').length,
                    dialogs: document.querySelectorAll('.el-overlay-dialog').length,
                    buttons: document.querySelectorAll('button').length,
                    body: clean(document.body && document.body.innerText).slice(0, 500),
                  };
                }
                """
            )
        except Exception:
            state = {
                "url": getattr(page, "url", "<unavailable>"),
                "tabs": "?",
                "inputs": "?",
                "dialogs": "?",
                "buttons": "?",
                "body": "<unavailable>",
            }
        self._log(
            "steamdt_debug "
            f"step={step_name} title={_compact_debug_text(title)} "
            f"url={_compact_debug_text(str(state.get('url')))} "
            f"tabs={state.get('tabs')} inputs={state.get('inputs')} "
            f"dialogs={state.get('dialogs')} buttons={state.get('buttons')} "
            f"body={_compact_debug_text(str(state.get('body')), max_length=500)}"
        )

    async def _extract_rows(self, page: Any) -> list[dict[str, Any]]:
        rows = await page.evaluate(
            """
            () => {
              const clean = (value) => String(value || '').trim();
              const linksFrom = (node) => Array.from(node.querySelectorAll('a[href]'))
                .map((a) => a.href)
                .filter(Boolean);
              const textLinesFrom = (node) => clean(node.innerText)
                .split('\\n')
                .map(clean)
                .filter(Boolean);
              const tableRows = Array.from(
                document.querySelectorAll('.el-table__body .el-table__row')
              ).map((row) => ({
                cells: Array.from(row.querySelectorAll('td'))
                  .map((td) => td.innerText),
                links: linksFrom(row),
              }));
              const cardScopes = new Map();
              for (const card of document.querySelectorAll('.market-item')) {
                const scope = card.closest('.el-table__expanded-cell, .el-table__row, tr')
                  || card.parentElement
                  || card;
                if (!cardScopes.has(scope)) {
                  cardScopes.set(scope, []);
                }
                cardScopes.get(scope).push(card);
              }
              const cardRows = Array.from(cardScopes.entries()).map(([scope, cards]) => ({
                cells: textLinesFrom(scope),
                links: linksFrom(scope),
                market_cards: cards.map((card) => ({
                  text: clean(card.innerText),
                  links: linksFrom(card),
                })),
              }));
              const rows = [...cardRows, ...tableRows];
              const seen = new Set();
              return rows.filter((row) => {
                const key = JSON.stringify([row.cells, row.links]);
                if (seen.has(key)) {
                  return false;
                }
                seen.add(key);
                return row.cells.length > 0 || row.links.length > 0;
              });
            }
            """
        )
        if not rows:
            rows = await page.evaluate(
                """
                () => Array.from(document.querySelectorAll('tr'))
                  .map((row) => ({
                    cells: Array.from(row.querySelectorAll('td')).map((td) => td.innerText),
                    links: Array.from(row.querySelectorAll('a[href]')).map((a) => a.href)
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
    seen: set[tuple[str, str | None, str | None]] = set()
    for row in rows:
        candidate = parse_steamdt_row(
            row,
            steam_sale_fee_rate=steam_sale_fee_rate,
            withdrawal_fee_rate=withdrawal_fee_rate,
        )
        if candidate is None:
            continue
        key = (candidate.market_hash_name, candidate.buff_url, candidate.steam_url)
        if key in seen:
            continue
        seen.add(key)
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
    if row.get("market_cards"):
        card_candidate = _parse_steamdt_card_row(
            row,
            steam_sale_fee_rate=steam_sale_fee_rate,
            withdrawal_fee_rate=withdrawal_fee_rate,
        )
        if card_candidate is not None:
            return card_candidate

    cells = tuple(clean_text(value) for value in row.get("cells", ()))
    links = tuple(str(value) for value in row.get("links", ()))
    if len(cells) < 4:
        return _parse_steamdt_card_row(
            row,
            steam_sale_fee_rate=steam_sale_fee_rate,
            withdrawal_fee_rate=withdrawal_fee_rate,
        )

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
    if quality is None:
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


def _parse_steamdt_card_row(
    row: dict[str, Any],
    *,
    steam_sale_fee_rate: Decimal,
    withdrawal_fee_rate: Decimal,
) -> SteamDTCandidate | None:
    cards = row.get("market_cards")
    if not isinstance(cards, list):
        return None

    cells = tuple(clean_text(value) for value in row.get("cells", ()))
    links = tuple(str(value) for value in row.get("links", ()))
    buff_url = _find_url(links, "buff.163.com")
    steam_url = _find_url(links, "steamcommunity.com/market/listings")
    steam_market_hash = parse_market_hash_from_steam_url(steam_url)
    display_text = _find_skin_like_text(cells)

    if steam_market_hash:
        item_name, quality, stattrak = parse_item_text(steam_market_hash)
        candidate_market_hash = steam_market_hash
    elif display_text:
        item_name, quality, stattrak = parse_item_text(display_text)
        candidate_market_hash = market_hash_name(item_name, quality)
    else:
        return None

    if _should_skip_item(item_name):
        return None
    if quality is None:
        return None

    buff_price = _price_from_cards(cards, "buff.163.com", "buff")
    steam_price = _price_from_cards(cards, "steamcommunity.com/market/listings", "steam")

    return SteamDTCandidate(
        item_name=item_name,
        market_hash_name=candidate_market_hash,
        display_name=(
            display_text if display_text and display_text != candidate_market_hash else None
        ),
        quality=quality,
        stattrak=stattrak,
        item_url=_find_url(links, "steamdt.com") or _find_url(links, "/item/"),
        buff_url=buff_url,
        steam_url=steam_url,
        currency=detect_currency(" ".join(cells)),
        buff_price=buff_price,
        steam_price=steam_price,
        profit=calculate_gross_profit(buff_price, steam_price),
        profitability_percent=calculate_gross_roi_percent(buff_price, steam_price),
        net_profit=calculate_net_profit(
            buff_price,
            steam_price,
            steam_sale_fee_rate=steam_sale_fee_rate,
            withdrawal_fee_rate=withdrawal_fee_rate,
        ),
        net_roi_percent=calculate_net_roi_percent(
            buff_price,
            steam_price,
            steam_sale_fee_rate=steam_sale_fee_rate,
            withdrawal_fee_rate=withdrawal_fee_rate,
        ),
        break_even_steam_price=calculate_break_even_steam_price(
            buff_price,
            steam_sale_fee_rate=steam_sale_fee_rate,
            withdrawal_fee_rate=withdrawal_fee_rate,
        ),
        volume=_volume_from_buff_card(cards),
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


def _find_skin_like_text(cells: tuple[str, ...]) -> str | None:
    for cell in cells:
        if " | " not in cell:
            continue
        lowered = cell.lower()
        if "skin flip" in lowered or "arbitrage" in lowered:
            continue
        return cell
    return None


def _price_from_cards(
    cards: list[Any],
    url_pattern: str,
    label_pattern: str,
) -> Decimal | None:
    for card in cards:
        if not isinstance(card, dict):
            continue
        text = clean_text(card.get("text", ""))
        links = tuple(str(value) for value in card.get("links", ()))
        lowered = text.lower()
        if _find_url(links, url_pattern) or label_pattern in lowered:
            return parse_market_decimal(text)
    return None


def _volume_from_buff_card(cards: list[Any]) -> int | None:
    for card in cards:
        if not isinstance(card, dict):
            continue
        text = clean_text(card.get("text", ""))
        links = tuple(str(value) for value in card.get("links", ()))
        if _find_url(links, "buff.163.com") or "buff" in text.lower():
            match = re.search(r"for\s+sale\s*[:：]?\s*([0-9][0-9,]*)", text, re.IGNORECASE)
            if match:
                return parse_int_from_text(match.group(1))
    return None


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


def _compact_debug_text(value: str, *, max_length: int = 160) -> str:
    text = " ".join(value.split())
    if len(text) <= max_length:
        return text
    return f"{text[: max_length - 3]}..."


def save_candidates(path: str | Path, candidates: tuple[SteamDTCandidate, ...]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            [_candidate_to_public_row(candidate) for candidate in candidates],
            default=str,
            indent=2,
        ),
        encoding="utf-8",
    )


def _candidate_to_public_row(candidate: SteamDTCandidate) -> dict[str, Any]:
    row = {
        "item_name": candidate.item_name,
        "market_hash_name": candidate.market_hash_name,
        "quality": candidate.quality,
        "stattrak": candidate.stattrak,
        "steam_url": candidate.steam_url,
        "buff_url": candidate.buff_url,
        "currency": candidate.currency,
        "buff_price": candidate.buff_price,
        "steam_price": candidate.steam_price,
        "profit": candidate.profit,
        "profitability_percent": candidate.profitability_percent,
        "net_profit": candidate.net_profit,
        "net_roi_percent": candidate.net_roi_percent,
        "break_even_steam_price": candidate.break_even_steam_price,
        "volume": candidate.volume,
        "strategy_id": candidate.strategy_id,
        "strategy_label": candidate.strategy_label,
        "balance_type": candidate.balance_type,
        "buy_mode": candidate.buy_mode,
        "sell_mode": candidate.sell_mode,
    }
    return {
        key: value
        for key, value in row.items()
        if value is not None and value != "" and value != ()
    }

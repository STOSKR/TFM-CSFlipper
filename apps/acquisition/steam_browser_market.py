"""Steam Market browser scraper with verbose diagnostics."""

from __future__ import annotations

import asyncio
import json
import random
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.parse import quote

from packages.contracts.observations import MarketObservationContract
from packages.domain.canonical_id import build_canonical_asset_id
from packages.domain.enums import SourceType
from packages.domain.market_parsing import (
    asset_name_from_market_hash,
    detect_currency,
    parse_int_from_text,
    parse_market_decimal,
    parse_required_market_decimal,
    quality_from_market_hash,
    variant_key,
)

STEAM_LISTING_URL = "https://steamcommunity.com/market/listings/730/{market_hash_name}"
MONEY_PATTERN = re.compile(
    r"(?:CNY|USD|EUR|GBP|PLN|\$|\u20ac|\u00a3|\u00a5|\uffe5|z\u0142)\s*\d[\d.,]*"
    r"|\d[\d.,]*\s*(?:CNY|USD|EUR|GBP|PLN|\u20ac|\u00a3|\u00a5|\uffe5|z\u0142)",
    re.IGNORECASE,
)
QUALITY_NAMES = (
    "Factory New",
    "Minimal Wear",
    "Field-Tested",
    "Well-Worn",
    "Battle-Scarred",
)
STEAM_PRICE_SELECTORS = (
    "[data-selected]",
    "#market_commodity_forsale .market_commodity_orders_header_promote",
    "#market_commodity_forsale_table .market_listing_price",
    ".market_listing_price",
    ".market_commodity_orders_header_promote",
    ".market_listing_their_price",
)
LogCallback = Callable[[str], None]


class SteamBrowserError(RuntimeError):
    """Raised when the Steam browser scraper cannot return a usable observation."""


@dataclass(frozen=True, slots=True)
class SteamBrowserCandidate:
    market_hash_name: str
    steam_url: str | None = None
    asset_name: str | None = None
    quality: str | None = None
    stattrak: bool = False
    category: str | None = None


@dataclass(frozen=True, slots=True)
class SteamBrowserObservation:
    observation: MarketObservationContract
    asset_name: str
    category: str | None
    quality: str | None
    variant_key: str


@dataclass(frozen=True, slots=True)
class SteamBrowserCandidateError:
    candidate: SteamBrowserCandidate
    message: str
    debug_log: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SteamBrowserConnectorConfig:
    headless: bool = True
    timeout_ms: int = 30000
    wait_after_load_ms: int = 3500
    manual_login_wait_ms: int = 0
    min_delay_seconds: float = 0.0
    max_delay_seconds: float = 0.0
    max_concurrency: int = 1
    session_state_path: Path | None = Path("data/browser-state/steam_storage_state.json")


class SteamBrowserConnector:
    """Playwright connector for Steam Market item pages."""

    def __init__(
        self,
        config: SteamBrowserConnectorConfig | None = None,
        *,
        log: LogCallback | None = None,
        progress_log: LogCallback | None = None,
    ) -> None:
        self._config = config or SteamBrowserConnectorConfig()
        self._log = log
        self._progress_log = progress_log

    async def fetch_candidates_lenient(
        self,
        candidates: list[SteamBrowserCandidate],
        *,
        correlation_id: str,
    ) -> tuple[tuple[SteamBrowserObservation, ...], tuple[SteamBrowserCandidateError, ...]]:
        if not candidates:
            return (), ()

        try:
            from playwright.async_api import async_playwright
        except ModuleNotFoundError as exc:  # pragma: no cover - environment dependent
            raise SteamBrowserError(
                "Playwright is required. Run: python -m pip install playwright"
            ) from exc

        async with async_playwright() as playwright:
            self._emit_browser_progress("launch_start")
            browser = await playwright.chromium.launch(
                headless=self._config.headless,
                timeout=self._config.timeout_ms,
            )
            self._emit_browser_progress("launch_ready")
            context_options: dict[str, Any] = {
                "viewport": {"width": 1920, "height": 1080},
                "user_agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123 Safari/537.36"
                ),
            }
            if self._config.session_state_path and self._config.session_state_path.exists():
                context_options["storage_state"] = str(self._config.session_state_path)
            self._emit_browser_progress("context_start")
            try:
                context = await asyncio.wait_for(
                    browser.new_context(**context_options),
                    timeout=self._config.timeout_ms / 1000,
                )
            except Exception:
                await browser.close()
                raise
            self._emit_browser_progress("context_ready")
            semaphore = asyncio.Semaphore(self._config.max_concurrency)

            async def fetch_one(
                index: int,
                candidate: SteamBrowserCandidate,
            ) -> SteamBrowserObservation | SteamBrowserCandidateError:
                async with semaphore:
                    debug_log: list[str] = []
                    self._emit_fetch_start(
                        index=index,
                        total=len(candidates),
                        candidate=candidate,
                    )
                    try:
                        return await asyncio.wait_for(
                            self._fetch_one(
                                context,
                                candidate,
                                correlation_id=correlation_id,
                                debug_log=debug_log,
                            ),
                            timeout=self._candidate_timeout_seconds(),
                        )
                    except Exception as exc:
                        message = str(exc) or exc.__class__.__name__
                        self._emit(candidate.market_hash_name, f"ERROR {message}")
                        return SteamBrowserCandidateError(
                            candidate=candidate,
                            message=message,
                            debug_log=tuple(debug_log),
                        )

            try:
                tasks = [
                    asyncio.create_task(fetch_one(index, candidate))
                    for index, candidate in enumerate(candidates, start=1)
                ]
                results = []
                ok_count = 0
                error_count = 0
                for completed, task in enumerate(asyncio.as_completed(tasks), start=1):
                    result = await task
                    results.append(result)
                    if isinstance(result, SteamBrowserObservation):
                        ok_count += 1
                    else:
                        error_count += 1
                    self._emit_progress(
                        completed=completed,
                        total=len(candidates),
                        ok_count=ok_count,
                        error_count=error_count,
                        result=result,
                    )
            finally:
                await self._save_session_state(context)
                await context.close()
                await browser.close()

        observations = tuple(
            result for result in results if isinstance(result, SteamBrowserObservation)
        )
        errors = tuple(
            result for result in results if isinstance(result, SteamBrowserCandidateError)
        )
        return observations, errors

    async def _fetch_one(
        self,
        context: Any,
        candidate: SteamBrowserCandidate,
        *,
        correlation_id: str,
        debug_log: list[str],
    ) -> SteamBrowserObservation:
        await self._sleep_between_requests()
        url = _steam_listing_url(candidate)
        self._debug(candidate.market_hash_name, debug_log, f"opening {url}")
        page = await context.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=self._config.timeout_ms)
            if self._config.manual_login_wait_ms > 0:
                self._debug(
                    candidate.market_hash_name,
                    debug_log,
                    f"waiting {self._config.manual_login_wait_ms}ms for manual login",
                )
                await page.wait_for_timeout(self._config.manual_login_wait_ms)
            await page.wait_for_timeout(self._config.wait_after_load_ms)
            quality = candidate.quality or quality_from_market_hash(candidate.market_hash_name)
            stattrak = candidate.stattrak or candidate.market_hash_name.lower().startswith(
                "stattrak"
            )
            souvenir = candidate.market_hash_name.lower().startswith("souvenir")
            await _select_new_market_variant(
                page,
                quality=quality,
                stattrak=stattrak,
                souvenir=souvenir,
                debug_log=debug_log,
            )
            await _select_chart_range(page, range_label="Lifetime", debug_log=debug_log)
            payload = await page.evaluate(
                f"""
                async (marketHashName) => {{
                  const fetchOrderBook = async () => {{
                    const params = new URLSearchParams({{
                      q: "Load",
                      qp: JSON.stringify([730, marketHashName])
                    }});
                    try {{
                      const response = await fetch(`/market/orderbook?${{params.toString()}}`, {{
                        credentials: "include",
                        headers: {{ accept: "application/json" }}
                      }});
                      return {{
                        status: response.status,
                        text: await response.text()
                      }};
                    }} catch (error) {{
                      return {{
                        status: 0,
                        text: "",
                        error: String(error)
                      }};
                    }}
                  }};
                  return {{
                  url: location.href,
                  title: document.title,
                  bodyText: document.body ? document.body.innerText : "",
                  ssrLoaderData: globalThis.SSR && Array.isArray(globalThis.SSR.loaderData)
                    ? globalThis.SSR.loaderData
                    : [],
                  selectorTexts: {list(STEAM_PRICE_SELECTORS)!r}.flatMap((selector) =>
                    Array.from(document.querySelectorAll(selector)).map((el) => ({{
                      selector,
                      text: el.innerText
                    }}))
                  ),
                  buyOrderRows: Array.from(
                    document.querySelectorAll('#market_commodity_buyrequests tr')
                  ).map((row) =>
                    Array.from(row.querySelectorAll('td')).map((cell) => cell.innerText)
                  ),
                  recentSalesChart: (() => {{
                    const clean = (value) => String(value || "").replace(/\\s+/g, " ").trim();
                    const moneyPattern = new RegExp(
                      "(?:CNY|USD|EUR|GBP|PLN|[$€£¥￥]|zł)\\\\s*\\\\d"
                      + "|\\\\d[\\\\d.,]*\\\\s*(?:CNY|USD|EUR|GBP|PLN|[$€£¥￥]|zł)",
                      "i"
                    );
                    const svgs = Array.from(document.querySelectorAll("svg.recharts-surface"));
                    const svg = svgs.find((node) => {{
                      const text = clean(node.textContent);
                      return text.includes("Price") && text.includes("Volume");
                    }});
                    if (!svg) {{
                      return null;
                    }}
                    const priceLinePaths = Array.from(
                      svg.querySelectorAll("path.recharts-line-curve")
                    ).map((path) => path.getAttribute("d"));
                    const texts = Array.from(svg.querySelectorAll("text")).map((node) => ({{
                      text: clean(node.textContent),
                      x: Number(node.getAttribute("x")),
                      y: Number(node.getAttribute("y")),
                    }}));
                    const clipRect = svg.querySelector("defs clipPath rect");
                    const selectedRange = Array.from(
                      document.querySelectorAll('[data-selected="true"]')
                    )
                      .map((node) => clean(node.textContent))
                      .find((text) => ["Week", "Month", "Year", "Lifetime"].includes(text));
                    return {{
                      selected_range: selectedRange || null,
                      plot_area: clipRect ? {{
                        x: Number(clipRect.getAttribute("x")),
                        y: Number(clipRect.getAttribute("y")),
                        width: Number(clipRect.getAttribute("width")),
                        height: Number(clipRect.getAttribute("height")),
                      }} : null,
                      price_line_path: priceLinePaths[0] || null,
                      price_line_paths: priceLinePaths,
                      price_ticks: texts.filter((entry) => moneyPattern.test(entry.text)),
                      time_ticks: texts.filter((entry) =>
                        /\\d{{1,2}}\\/\\d{{1,2}}\\/\\d{{4}}/.test(entry.text)
                      ),
                    }};
                  }})(),
                  orderBook: await fetchOrderBook()
                  }};
                }}
                """,
                candidate.market_hash_name,
            )
        finally:
            await page.close()

        title = str(payload.get("title") or "")
        body_text = str(payload.get("bodyText") or "")
        ssr_loader_data = list(payload.get("ssrLoaderData") or [])
        selector_texts = list(payload.get("selectorTexts") or [])
        buy_order_rows = list(payload.get("buyOrderRows") or [])
        chart_payload = payload.get("recentSalesChart")
        orderbook_payload = _json_payload(payload.get("orderBook"))
        self._debug(candidate.market_hash_name, debug_log, f"title={title!r}")
        self._debug(
            candidate.market_hash_name,
            debug_log,
            f"selector_matches={len(selector_texts)} body_chars={len(body_text)}",
        )

        quality = candidate.quality or quality_from_market_hash(candidate.market_hash_name)
        stattrak = candidate.stattrak or candidate.market_hash_name.lower().startswith("stattrak")
        price_text = extract_steam_price_text(
            selector_texts,
            body_text,
            quality=quality,
            stattrak=stattrak,
            market_hash_name=candidate.market_hash_name,
            ssr_loader_data=ssr_loader_data,
            debug_log=debug_log,
        )
        if not price_text:
            excerpt = " ".join(body_text.split())[:300]
            self._debug(candidate.market_hash_name, debug_log, f"body_excerpt={excerpt!r}")
            raise SteamBrowserError(
                "Steam price not found: no selector/fallback contained a money value"
            )

        self._debug(candidate.market_hash_name, debug_log, f"price_text={price_text!r}")
        asset_name = candidate.asset_name or asset_name_from_market_hash(candidate.market_hash_name)
        asset_id = build_canonical_asset_id(name=asset_name, quality=quality, stattrak=stattrak)
        currency = detect_currency(price_text, default="EUR") or "EUR"
        observation = MarketObservationContract(
            correlation_id=correlation_id,
            asset_id=asset_id,
            platform_id="steam",
            observed_at=datetime.now(tz=UTC),
            price=parse_required_market_decimal(price_text),
            currency=currency,
            source_type=SourceType.SCRAPING,
            volume=parse_int_from_text(_find_volume_text(body_text)),
            source_reference=url,
            raw_payload={
                "market_hash_name": candidate.market_hash_name,
                "steam_url": url,
                "price_text": price_text,
                "buy_orders": extract_steam_orderbook_buy_orders(
                    orderbook_payload,
                    currency=currency,
                )
                or extract_steam_buy_orders(buy_order_rows),
                "recent_sales": extract_steam_recent_sales(
                    chart_payload,
                    quality=quality,
                    limit=None,
                ),
                "page_title": title,
                "debug_log": tuple(debug_log),
            },
        )
        return SteamBrowserObservation(
            observation=observation,
            asset_name=asset_name,
            category=candidate.category,
            quality=quality,
            variant_key=variant_key(quality, stattrak),
        )

    async def _save_session_state(self, context: Any) -> None:
        if not self._config.session_state_path:
            return
        self._config.session_state_path.parent.mkdir(parents=True, exist_ok=True)
        await context.storage_state(path=str(self._config.session_state_path))

    async def _sleep_between_requests(self) -> None:
        if self._config.max_delay_seconds <= 0:
            return
        delay = random.uniform(
            max(0.0, self._config.min_delay_seconds),
            max(self._config.min_delay_seconds, self._config.max_delay_seconds),
        )
        await asyncio.sleep(delay)

    def _candidate_timeout_seconds(self) -> float:
        return (
            self._config.timeout_ms
            + self._config.wait_after_load_ms
            + self._config.manual_login_wait_ms
        ) / 1000 + max(0.0, self._config.max_delay_seconds) + 15.0

    def _debug(self, item: str, debug_log: list[str], message: str) -> None:
        debug_log.append(message)
        self._emit(item, message)

    def _emit(self, item: str, message: str) -> None:
        if self._log:
            self._log(f"[steam] {item}: {message}")

    def _emit_progress(
        self,
        *,
        completed: int,
        total: int,
        ok_count: int,
        error_count: int,
        result: SteamBrowserObservation | SteamBrowserCandidateError,
    ) -> None:
        if self._progress_log is None:
            return
        if isinstance(result, SteamBrowserObservation):
            item = result.observation.raw_payload.get("market_hash_name") or result.asset_name
            state = "ok"
        else:
            item = result.candidate.market_hash_name
            state = "error"
        self._progress_log(
            "steam_progress="
            f"{completed}/{total} ok={ok_count} errors={error_count} "
            f"state={state} last={_compact_log_text(str(item))}"
        )

    def _emit_fetch_start(
        self,
        *,
        index: int,
        total: int,
        candidate: SteamBrowserCandidate,
    ) -> None:
        if self._progress_log is None:
            return
        self._progress_log(
            "steam_fetch_start="
            f"{index}/{total} item={_compact_log_text(candidate.market_hash_name)}"
        )

    def _emit_browser_progress(self, step: str) -> None:
        if self._progress_log is not None:
            self._progress_log(f"steam_browser={step}")


def extract_steam_price_text(
    selector_texts: list[Any],
    body_text: str,
    *,
    quality: str | None = None,
    stattrak: bool = False,
    market_hash_name: str | None = None,
    ssr_loader_data: list[Any] | None = None,
    debug_log: list[str] | None = None,
) -> str | None:
    """Extract the first visible Steam sell price from selector hits or page text."""

    bucket_price = _extract_bucket_price_text(
        ssr_loader_data or (),
        market_hash_name=market_hash_name,
        quality=quality,
        stattrak=stattrak,
        debug_log=debug_log,
    )
    if bucket_price:
        return bucket_price

    if quality:
        for entry in selector_texts:
            text = str(entry.get("text") if isinstance(entry, dict) else entry)
            price = _extract_quality_block_price(
                text,
                quality=quality,
                stattrak=stattrak,
                debug_log=debug_log,
                source="quality card",
            )
            if price:
                return price

        price = _extract_quality_block_price(
            body_text,
            quality=quality,
            stattrak=stattrak,
            debug_log=debug_log,
            source="body quality block",
        )
        if price:
            return price

    for entry in selector_texts:
        text = str(entry.get("text") if isinstance(entry, dict) else entry)
        match = MONEY_PATTERN.search(text)
        if match:
            _append_debug(debug_log, f"price matched selector text={text!r}")
            return match.group(0)

    preferred_labels = ("starting at", "lowest price", "price", "starting from")
    for line in (line.strip() for line in body_text.splitlines() if line.strip()):
        lowered = line.lower()
        if any(label in lowered for label in preferred_labels):
            match = MONEY_PATTERN.search(line)
            if match:
                _append_debug(debug_log, f"price matched fallback line={line!r}")
                return match.group(0)

    match = MONEY_PATTERN.search(body_text)
    if match:
        _append_debug(debug_log, "price matched raw body fallback")
        return match.group(0)
    return None


def extract_steam_buy_orders(rows: list[Any]) -> tuple[dict[str, str | int], ...]:
    buy_orders: list[dict[str, str | int]] = []
    for row in rows:
        if not isinstance(row, list) or len(row) < 2:
            continue
        row_text = " ".join(str(cell) for cell in row)
        price_match = MONEY_PATTERN.search(row_text)
        if not price_match:
            continue
        quantity = _first_int_after(row_text, price_match.end())
        if quantity is None:
            continue
        buy_orders.append({"price": price_match.group(0), "quantity": quantity})
    return tuple(buy_orders)


def extract_steam_orderbook_buy_orders(
    payload: object,
    *,
    currency: str | None = None,
    limit: int = 20,
) -> tuple[dict[str, str | int], ...]:
    if not isinstance(payload, dict) or payload.get("success") is not True:
        return ()
    data = payload.get("data")
    if not isinstance(data, dict):
        return ()
    compact_orders = data.get("rgCompactBuyOrders")
    if not isinstance(compact_orders, list):
        return ()

    rows: list[dict[str, str | int]] = []
    currency_prefix = (currency or "").strip().upper()
    for index in range(0, len(compact_orders) - 1, 2):
        if len(rows) >= limit:
            break
        amount = _decimal_from_compact_order_value(compact_orders[index])
        quantity = _int_from_compact_order_value(compact_orders[index + 1])
        if amount is None or quantity is None:
            continue
        price = str(amount.quantize(Decimal("0.01")))
        rows.append(
            {
                "source": "steam_orderbook",
                "price": f"{currency_prefix} {price}" if currency_prefix else price,
                "quantity": quantity,
            }
        )
    return tuple(rows)


def extract_steam_recent_sales(
    chart_payload: object,
    *,
    quality: str | None = None,
    limit: int | None = None,
) -> tuple[dict[str, Any], ...]:
    if not isinstance(chart_payload, dict):
        return ()
    price_line_path = _price_line_path_for_quality(chart_payload, quality=quality)
    if not isinstance(price_line_path, str) or not price_line_path.strip():
        return ()
    price_scale = _price_scale_from_ticks(chart_payload.get("price_ticks"))
    if price_scale is None:
        return ()
    time_ticks = _time_ticks(chart_payload.get("time_ticks"))
    selected_range = _optional_str(chart_payload.get("selected_range"))
    points = _path_points(price_line_path)
    if limit is not None:
        selected_points = points[-max(1, limit) :]
        start_index = max(0, len(points) - limit)
    else:
        selected_points = points
        start_index = 0
    rows: list[dict[str, Any]] = []
    last_observed_at: datetime | None = None
    for index, (x, y) in enumerate(selected_points, start=start_index):
        observed_time = _steam_point_time(x, time_ticks)
        if observed_time is not None:
            observed_time = _normalize_steam_point_time(observed_time)
            if last_observed_at is not None and observed_time <= last_observed_at:
                observed_time = last_observed_at + timedelta(hours=1)
            last_observed_at = observed_time
        estimated_at = (
            _format_steam_time_label(observed_time)
            if observed_time is not None
            else _nearest_time_label(x, time_ticks)
        )
        row: dict[str, Any] = {
            "source": "steam_recharts",
            "granularity": "point",
            "point_index": index,
            "price": str(_price_from_y(y, price_scale).quantize(Decimal("0.01"))),
            "time_label": estimated_at,
        }
        if observed_time is not None:
            row["observed_at"] = observed_time.replace(tzinfo=UTC).isoformat()
        if selected_range:
            row["range"] = selected_range
        rows.append(row)
    return tuple(rows)


def _first_int_after(value: str, start: int) -> int | None:
    match = re.search(r"\d[\d.,]*", value[start:])
    if not match:
        return None
    digits = re.sub(r"[^0-9]", "", match.group(0))
    return int(digits) if digits else None


async def _select_new_market_variant(
    page: Any,
    *,
    quality: str | None,
    stattrak: bool,
    souvenir: bool,
    debug_log: list[str],
) -> None:
    selected = await page.evaluate(
        """
        async ({quality, stattrak, souvenir}) => {
          const clean = (value) => String(value || "").replace(/\\s+/g, " ").trim();
          const click = (node) => {
            if (!node) return false;
            node.dispatchEvent(new MouseEvent("click", {
              bubbles: true,
              cancelable: true,
              view: window
            }));
            return true;
          };
          const clickSwitchBeside = (label, shouldEnable) => {
            const labels = Array.from(document.querySelectorAll("span, div"))
              .filter((node) => clean(node.innerText || node.textContent) === label);
            for (const labelNode of labels) {
              const wrapper = labelNode.parentElement;
              const switchNode = wrapper && wrapper.querySelector('[role="switch"]');
              if (!switchNode) continue;
              const enabled = switchNode.getAttribute("aria-checked") === "true";
              if (enabled !== shouldEnable) {
                return click(switchNode);
              }
              return true;
            }
            return false;
          };
          const stattrakClicked = clickSwitchBeside("StatTrak™", Boolean(stattrak));
          const souvenirClicked = clickSwitchBeside("Souvenir", Boolean(souvenir));
          await new Promise((resolve) => setTimeout(resolve, 750));
          let qualityClicked = false;
          if (quality) {
            const tabs = Array.from(document.querySelectorAll("[data-selected]"))
              .filter((node) => clean(node.innerText || node.textContent).includes(quality));
            qualityClicked = click(tabs[0]);
          }
          await new Promise((resolve) => setTimeout(resolve, 1200));
          return {stattrakClicked, souvenirClicked, qualityClicked};
        }
        """,
        {"quality": quality, "stattrak": stattrak, "souvenir": souvenir},
    )
    debug_log.append(f"new_market_variant_selection={selected!r}")


async def _select_chart_range(
    page: Any,
    *,
    range_label: str,
    debug_log: list[str],
) -> None:
    selected = await page.evaluate(
        """
        async (rangeLabel) => {
          const clean = (value) => String(value || "").replace(/\\s+/g, " ").trim();
          const options = Array.from(document.querySelectorAll("[data-selected]"));
          const node = options.find((element) =>
            clean(element.innerText || element.textContent) === rangeLabel
          );
          if (!node) {
            return {clicked: false};
          }
          const alreadySelected = node.getAttribute("data-selected") === "true";
          if (!alreadySelected) {
            node.dispatchEvent(new MouseEvent("click", {
              bubbles: true,
              cancelable: true,
              view: window
            }));
            await new Promise((resolve) => setTimeout(resolve, 1600));
          }
          return {clicked: !alreadySelected, alreadySelected};
        }
        """,
        range_label,
    )
    debug_log.append(f"chart_range_selection={selected!r}")


def _path_points(path_value: str) -> tuple[tuple[float, float], ...]:
    matches = re.findall(r"[ML]\s*([0-9.]+),([0-9.]+)", path_value)
    return tuple((float(x), float(y)) for x, y in matches)


def _price_scale_from_ticks(value: object) -> tuple[tuple[float, Decimal], ...] | None:
    if not isinstance(value, list):
        return None
    points: list[tuple[float, Decimal]] = []
    for row in value:
        if not isinstance(row, dict):
            continue
        y = row.get("y")
        text = row.get("text")
        price = parse_market_decimal(str(text or ""))
        if not isinstance(y, int | float) or price is None:
            continue
        points.append((float(y), price))
    unique = tuple(sorted(set(points), key=lambda item: item[0]))
    return unique if len(unique) >= 2 else None


def _price_from_y(y: float, scale: tuple[tuple[float, Decimal], ...]) -> Decimal:
    y1, price1 = scale[0]
    y2, price2 = scale[-1]
    if y1 == y2:
        return price1
    ratio = Decimal(str((y - y1) / (y2 - y1)))
    return price1 + (price2 - price1) * ratio


def _time_ticks(value: object) -> tuple[tuple[float, str], ...]:
    if not isinstance(value, list):
        return ()
    rows: list[tuple[float, str]] = []
    for row in value:
        if not isinstance(row, dict):
            continue
        x = row.get("x")
        text = _optional_str(row.get("text"))
        if isinstance(x, int | float) and text:
            rows.append((float(x), text))
    return tuple(rows)


def _nearest_time_label(x: float, ticks: tuple[tuple[float, str], ...]) -> str | None:
    if not ticks:
        return None
    return min(ticks, key=lambda item: abs(item[0] - x))[1]


def _steam_point_time(x: float, ticks: tuple[tuple[float, str], ...]) -> datetime | None:
    interpolated = _interpolated_time(x, ticks)
    if interpolated is not None:
        return interpolated
    nearest_label = _nearest_time_label(x, ticks)
    return _parse_steam_time_label(nearest_label) if nearest_label else None


def _interpolated_time(x: float, ticks: tuple[tuple[float, str], ...]) -> datetime | None:
    if len(ticks) < 2:
        return None
    sorted_ticks = sorted(ticks, key=lambda item: item[0])
    lower = sorted_ticks[0]
    upper = sorted_ticks[-1]
    for index, tick in enumerate(sorted_ticks):
        if tick[0] <= x:
            lower = tick
        if tick[0] >= x:
            upper = tick
            break
        if index == len(sorted_ticks) - 1:
            upper = tick
    lower_time = _parse_steam_time_label(lower[1])
    upper_time = _parse_steam_time_label(upper[1])
    if lower_time is None or upper_time is None or upper[0] == lower[0]:
        return None
    ratio = (x - lower[0]) / (upper[0] - lower[0])
    return lower_time + timedelta(
        seconds=(upper_time - lower_time).total_seconds() * ratio
    )


def _normalize_steam_point_time(value: datetime) -> datetime:
    return value.replace(minute=0, second=0, microsecond=0)


def _parse_steam_time_label(value: str) -> datetime | None:
    for date_format in (
        "%m/%d/%Y, %I %p",
        "%d/%m/%Y, %H",
        "%m/%d/%Y, %H",
        "%m/%d/%Y",
        "%d/%m/%Y",
    ):
        try:
            return datetime.strptime(value, date_format)
        except ValueError:
            continue
    return None


def _format_steam_time_label(value: datetime) -> str:
    return f"{value.month}/{value.day}/{value.year}, {value.strftime('%I').lstrip('0')} {value:%p}"


def _steam_time_label_iso(value: object) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    parsed = _parse_steam_time_label(text)
    if parsed is None:
        return None
    return parsed.replace(tzinfo=UTC).isoformat()


def _price_line_path_for_quality(chart_payload: dict[str, Any], *, quality: str | None) -> object:
    paths = chart_payload.get("price_line_paths")
    if not isinstance(paths, list) or not paths:
        return chart_payload.get("price_line_path")
    if quality in QUALITY_NAMES:
        index = QUALITY_NAMES.index(quality)
        if index < len(paths):
            return paths[index]
    return chart_payload.get("price_line_path") or paths[0]


def _optional_str(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _compact_log_text(value: str, *, max_length: int = 80) -> str:
    text = " ".join(value.split())
    if len(text) <= max_length:
        return text
    return f"{text[: max_length - 3]}..."


def _decimal_from_compact_order_value(value: object) -> Decimal | None:
    try:
        return Decimal(str(value)) / Decimal("100")
    except Exception:
        return None


def _int_from_compact_order_value(value: object) -> int | None:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def _json_payload(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    text = value.get("text")
    if not isinstance(text, str) or not text.strip():
        return {}
    try:
        payload = json.loads(text)
    except ValueError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _extract_bucket_price_text(
    ssr_loader_data: tuple[Any, ...] | list[Any],
    *,
    market_hash_name: str | None,
    quality: str | None,
    stattrak: bool,
    debug_log: list[str] | None,
) -> str | None:
    for bucket in _iter_steam_buckets(ssr_loader_data):
        if not isinstance(bucket, dict):
            continue
        bucket_name = str(bucket.get("bucket_id") or bucket.get("localized_name") or "")
        group_name = str(bucket.get("localized_name_inside_group") or "")
        if not _bucket_matches_candidate(
            bucket_name,
            group_name,
            market_hash_name=market_hash_name,
            quality=quality,
            stattrak=stattrak,
        ):
            continue
        price_text = str(bucket.get("strPrice") or "").strip()
        if price_text:
            _append_debug(debug_log, f"price matched SSR bucket bucket_id={bucket_name!r}")
            return price_text
        _append_debug(debug_log, f"SSR bucket had no strPrice bucket_id={bucket_name!r}")
    return None


def _iter_steam_buckets(values: tuple[Any, ...] | list[Any]) -> tuple[dict[str, Any], ...]:
    buckets: list[dict[str, Any]] = []
    stack = list(values)
    while stack:
        value = stack.pop()
        if isinstance(value, str):
            if "buckets" not in value:
                continue
            try:
                value = json.loads(value)
            except ValueError:
                continue
        if isinstance(value, dict):
            nested_buckets = value.get("buckets")
            if isinstance(nested_buckets, list):
                buckets.extend(bucket for bucket in nested_buckets if isinstance(bucket, dict))
            stack.extend(value.values())
        elif isinstance(value, list):
            stack.extend(value)
    return tuple(buckets)


def _bucket_matches_candidate(
    bucket_name: str,
    group_name: str,
    *,
    market_hash_name: str | None,
    quality: str | None,
    stattrak: bool,
) -> bool:
    if market_hash_name and _normalize_market_name(bucket_name) == _normalize_market_name(
        market_hash_name
    ):
        return True
    if not quality:
        return False
    normalized_group = _normalize_market_name(group_name)
    if _normalize_market_name(quality) not in normalized_group:
        return False
    group_is_stattrak = "stattrak" in normalized_group
    group_is_souvenir = "souvenir" in normalized_group
    return group_is_stattrak == stattrak and not group_is_souvenir


def _normalize_market_name(value: str) -> str:
    text = value.replace("\u2122", "")
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text


def _extract_quality_block_price(
    text: str,
    *,
    quality: str,
    stattrak: bool,
    debug_log: list[str] | None,
    source: str,
) -> str | None:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    quality_lower = quality.lower()
    for index, line in enumerate(lines):
        if line.lower() != quality_lower:
            continue
        block = [line]
        for next_line in lines[index + 1 :]:
            if next_line.lower() in {name.lower() for name in QUALITY_NAMES}:
                break
            block.append(next_line)
        block_text = "\n".join(block)
        prices = [str(price) for price in MONEY_PATTERN.findall(block_text)]
        if not prices:
            _append_debug(debug_log, f"{source} had no money text={block_text!r}")
            continue
        price_index = 1 if stattrak and len(prices) > 1 else 0
        _append_debug(
            debug_log,
            f"price matched {source} quality={quality!r} stattrak={stattrak}",
        )
        return prices[price_index]
    return None


def _find_volume_text(body_text: str) -> str | None:
    for line in body_text.splitlines():
        lowered = line.lower()
        if "volume" in lowered or "sold" in lowered:
            return line
    return None


def _append_debug(debug_log: list[str] | None, message: str) -> None:
    if debug_log is not None:
        debug_log.append(message)


def _steam_listing_url(candidate: SteamBrowserCandidate) -> str:
    market_hash_name = _steam_url_market_hash_name(candidate.market_hash_name)
    if candidate.steam_url:
        parsed_name = candidate.steam_url.rsplit("/market/listings/730/", maxsplit=1)[-1]
        parsed_name_lower = parsed_name.lower()
        if (
            candidate.stattrak
            and "stattrak" in parsed_name_lower
            and "%e2%84%a2" not in parsed_name_lower
        ):
            return STEAM_LISTING_URL.format(market_hash_name=quote(market_hash_name))
        return candidate.steam_url
    return STEAM_LISTING_URL.format(market_hash_name=quote(market_hash_name))


def _steam_url_market_hash_name(market_hash_name: str) -> str:
    if re.match(r"^stattrak(?!\u2122)", market_hash_name, flags=re.IGNORECASE):
        return re.sub(
            r"^stattrak",
            "StatTrak\u2122",
            market_hash_name,
            count=1,
            flags=re.IGNORECASE,
        )
    return market_hash_name

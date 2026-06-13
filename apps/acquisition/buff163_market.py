"""BUFF163 browser scraper with verbose diagnostics."""

from __future__ import annotations

import asyncio
import random
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from packages.contracts.observations import MarketObservationContract
from packages.domain.canonical_id import build_canonical_asset_id
from packages.domain.enums import SourceType
from packages.domain.market_parsing import (
    asset_name_from_market_hash,
    detect_currency,
    parse_market_decimal,
    parse_required_market_decimal,
    quality_from_market_hash,
    variant_key,
)

MONEY_PATTERN = re.compile(
    r"(?:CNY|USD|EUR|GBP|\$|\u20ac|\u00a3|\u00a5|\uffe5)\s*\d[\d.,]*"
    r"|\d[\d.,]*\s*(?:CNY|USD|EUR|GBP|\u20ac|\u00a3|\u00a5|\uffe5)",
    re.IGNORECASE,
)
LEADING_SYMBOL_MONEY_PATTERN = re.compile(r"(?:\$|\u20ac|\u00a3|\u00a5|\uffe5)\s*\d[\d.,]*")
BUFF_PRICE_SELECTORS = (
    ".detail-tab-cont .f_Strong",
    ".list_tb_csgo .f_Strong",
    ".market-card .f_Strong",
    ".selling .f_Strong",
    "[class*='price']",
)
LogCallback = Callable[[str], None]


class Buff163Error(RuntimeError):
    """Raised when BUFF163 cannot return a usable observation."""


@dataclass(frozen=True, slots=True)
class Buff163Candidate:
    market_hash_name: str
    buff_url: str
    asset_name: str | None = None
    quality: str | None = None
    stattrak: bool = False
    category: str | None = None


@dataclass(frozen=True, slots=True)
class Buff163Observation:
    observation: MarketObservationContract
    asset_name: str
    category: str | None
    quality: str | None
    variant_key: str


@dataclass(frozen=True, slots=True)
class Buff163CandidateError:
    candidate: Buff163Candidate
    message: str
    debug_log: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Buff163ConnectorConfig:
    headless: bool = True
    timeout_ms: int = 30000
    wait_after_load_ms: int = 2500
    manual_login_wait_ms: int = 0
    min_delay_seconds: float = 0.0
    max_delay_seconds: float = 0.0
    max_concurrency: int = 1
    session_state_path: Path | None = Path("data/browser-state/buff163_storage_state.json")


class Buff163Connector:
    """Playwright connector for BUFF163 item pages."""

    def __init__(
        self,
        config: Buff163ConnectorConfig | None = None,
        *,
        log: LogCallback | None = None,
    ) -> None:
        self._config = config or Buff163ConnectorConfig()
        self._log = log

    async def fetch_candidates(
        self,
        candidates: list[Buff163Candidate],
        *,
        correlation_id: str,
    ) -> tuple[Buff163Observation, ...]:
        observations, errors = await self.fetch_candidates_lenient(
            candidates,
            correlation_id=correlation_id,
        )
        if errors:
            first_error = errors[0]
            raise Buff163Error(
                f"BUFF request failed for {first_error.candidate.market_hash_name}: "
                f"{first_error.message}"
            )
        return observations

    async def fetch_candidates_lenient(
        self,
        candidates: list[Buff163Candidate],
        *,
        correlation_id: str,
    ) -> tuple[tuple[Buff163Observation, ...], tuple[Buff163CandidateError, ...]]:
        if not candidates:
            return (), ()

        try:
            from playwright.async_api import async_playwright
        except ModuleNotFoundError as exc:  # pragma: no cover - environment dependent
            raise Buff163Error(
                "Playwright is required. Run: python -m pip install playwright"
            ) from exc

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=self._config.headless)
            context_options: dict[str, Any] = {
                "viewport": {"width": 1920, "height": 1080},
                "user_agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123 Safari/537.36"
                ),
            }
            if self._config.session_state_path and self._config.session_state_path.exists():
                context_options["storage_state"] = str(self._config.session_state_path)
            context = await browser.new_context(**context_options)
            semaphore = asyncio.Semaphore(self._config.max_concurrency)

            async def fetch_one(
                candidate: Buff163Candidate,
            ) -> Buff163Observation | Buff163CandidateError:
                async with semaphore:
                    debug_log: list[str] = []
                    try:
                        return await self._fetch_one(
                            context,
                            candidate,
                            correlation_id=correlation_id,
                            debug_log=debug_log,
                        )
                    except Exception as exc:
                        self._emit(candidate.market_hash_name, f"ERROR {exc}")
                        return Buff163CandidateError(
                            candidate=candidate,
                            message=str(exc),
                            debug_log=tuple(debug_log),
                        )

            try:
                results = await asyncio.gather(*(fetch_one(candidate) for candidate in candidates))
            finally:
                await self._save_session_state(context)
                await context.close()
                await browser.close()

        observations = tuple(
            result for result in results if isinstance(result, Buff163Observation)
        )
        errors = tuple(
            result for result in results if isinstance(result, Buff163CandidateError)
        )
        return observations, errors

    async def _fetch_one(
        self,
        context: Any,
        candidate: Buff163Candidate,
        *,
        correlation_id: str,
        debug_log: list[str],
    ) -> Buff163Observation:
        await self._sleep_between_requests()
        self._debug(candidate.market_hash_name, debug_log, f"opening {candidate.buff_url}")
        page = await context.new_page()
        try:
            await page.goto(
                candidate.buff_url,
                wait_until="domcontentloaded",
                timeout=self._config.timeout_ms,
            )
            if self._config.manual_login_wait_ms > 0:
                self._debug(
                    candidate.market_hash_name,
                    debug_log,
                    f"waiting {self._config.manual_login_wait_ms}ms for manual login",
                )
                await page.wait_for_timeout(self._config.manual_login_wait_ms)
            await page.wait_for_timeout(self._config.wait_after_load_ms)
            payload = await page.evaluate(
                f"""
                () => ({{
                  url: location.href,
                  title: document.title,
                  bodyText: document.body ? document.body.innerText : "",
                  selectorTexts: {list(BUFF_PRICE_SELECTORS)!r}.flatMap((selector) =>
                    Array.from(document.querySelectorAll(selector)).map((el) => ({{
                      selector,
                      text: el.innerText
                    }}))
                  ),
                  buyOrderRows: Array.from(
                    document.querySelectorAll(
                      "tr, li, [class*='buy'], [class*='order'], [class*='demand']"
                    )
                  ).map((el) => ({{
                    tag: el.tagName,
                    className: el.className || "",
                    text: el.innerText || ""
                  }}))
                }})
                """
            )
        finally:
            await page.close()

        title = str(payload.get("title") or "")
        body_text = str(payload.get("bodyText") or "")
        selector_texts = list(payload.get("selectorTexts") or [])
        buy_order_rows = list(payload.get("buyOrderRows") or [])
        self._debug(candidate.market_hash_name, debug_log, f"title={title!r}")
        self._debug(
            candidate.market_hash_name,
            debug_log,
            f"selector_matches={len(selector_texts)} body_chars={len(body_text)}",
        )

        price_text = extract_buff_price_text(selector_texts, body_text, debug_log=debug_log)
        if not price_text:
            excerpt = " ".join(body_text.split())[:300]
            self._debug(candidate.market_hash_name, debug_log, f"body_excerpt={excerpt!r}")
            raise Buff163Error(f"BUFF price not found for {candidate.market_hash_name}")
        self._debug(candidate.market_hash_name, debug_log, f"price_text={price_text!r}")

        asset_name = candidate.asset_name or asset_name_from_market_hash(candidate.market_hash_name)
        quality = candidate.quality or quality_from_market_hash(candidate.market_hash_name)
        stattrak = candidate.stattrak or candidate.market_hash_name.lower().startswith("stattrak")
        asset_id = build_canonical_asset_id(name=asset_name, quality=quality, stattrak=stattrak)
        currency = detect_currency(price_text, default="CNY") or "CNY"
        observation = MarketObservationContract(
            correlation_id=correlation_id,
            asset_id=asset_id,
            platform_id="buff163",
            observed_at=datetime.now(tz=UTC),
            price=parse_required_market_decimal(price_text),
            currency=currency,
            source_type=SourceType.SCRAPING,
            source_reference=candidate.buff_url,
            raw_payload={
                "market_hash_name": candidate.market_hash_name,
                "buff_url": candidate.buff_url,
                "price_text": price_text,
                "buy_orders": extract_buff_buy_orders(
                    buy_order_rows,
                    body_text,
                    display_currency=currency,
                ),
                "page_title": title,
                "debug_log": tuple(debug_log),
            },
        )
        return Buff163Observation(
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

    def _debug(self, item: str, debug_log: list[str], message: str) -> None:
        debug_log.append(message)
        self._emit(item, message)

    def _emit(self, item: str, message: str) -> None:
        if self._log:
            self._log(f"[buff163] {item}: {message}")


def extract_buff_price_text(
    selector_texts_or_body: list[Any] | str,
    body_text: str | None = None,
    *,
    debug_log: list[str] | None = None,
) -> str | None:
    """Extract the first plausible money value from a BUFF item page."""

    if body_text is None:
        selector_texts: list[Any] = []
        body_text = str(selector_texts_or_body)
    else:
        selector_texts = (
            list(selector_texts_or_body)
            if isinstance(selector_texts_or_body, list)
            else []
        )

    for entry in selector_texts:
        text = str(entry.get("text") if isinstance(entry, dict) else entry)
        match = MONEY_PATTERN.search(text)
        if match:
            _append_debug(debug_log, f"price matched selector text={text!r}")
            return match.group(0)

    normalized_lines = [line.strip() for line in body_text.splitlines() if line.strip()]
    preferred_labels = (
        "sell",
        "selling",
        "lowest",
        "price",
        "\u51fa\u552e",
        "\u5728\u552e",
        "\u4ef7\u683c",
        "\u552e\u4ef7",
    )
    for line in normalized_lines:
        lowered = line.lower()
        if any(label in lowered for label in preferred_labels):
            match = MONEY_PATTERN.search(line)
            if match:
                _append_debug(debug_log, f"price matched fallback line={line!r}")
                return match.group(0)

    match = MONEY_PATTERN.search(body_text)
    if match:
        _append_debug(debug_log, "price matched raw body fallback")
    return match.group(0) if match else None


def extract_buff_buy_orders(
    rows: list[Any],
    body_text: str = "",
    *,
    display_currency: str | None = None,
) -> tuple[dict[str, str | int], ...]:
    buy_orders: dict[tuple[str, Decimal], dict[str, str | int]] = {}
    seen: set[tuple[str, int]] = set()
    for text in _buy_order_candidate_texts(rows, body_text):
        for price_text, price_end in _iter_money_candidates(text):
            currency = detect_currency(price_text, default="CNY") or "CNY"
            if display_currency and currency != display_currency.upper():
                continue
            price = parse_market_decimal(price_text)
            if price is None or not _is_plausible_buff_order_price(price_text, price):
                continue
            quantity = _first_int_after(text, price_end)
            if quantity is None:
                continue
            key = (price_text, quantity)
            if key in seen:
                continue
            seen.add(key)
            price_key = (currency, price)
            current = buy_orders.get(price_key)
            if current is None or quantity > int(current["quantity"]):
                buy_orders[price_key] = {"price": price_text, "quantity": quantity}
    return tuple(buy_orders.values())


def _buy_order_candidate_texts(rows: list[Any], body_text: str) -> tuple[str, ...]:
    labels = (
        "buy",
        "order",
        "purchase",
        "demand",
        "\u6c42\u8d2d",
        "\u6536\u8d2d",
        "\u8d2d\u4e70",
    )
    texts: list[str] = []
    for row in rows:
        text = ""
        if isinstance(row, dict):
            text = " ".join(
                str(row.get(key) or "")
                for key in ("className", "text")
            )
        elif isinstance(row, list):
            text = " ".join(str(cell) for cell in row)
        else:
            text = str(row)
        normalized = " ".join(text.split())
        if normalized and any(label in normalized.lower() for label in labels):
            texts.append(normalized)

    for line in body_text.splitlines():
        normalized = " ".join(line.split())
        if normalized and any(label in normalized.lower() for label in labels):
            texts.append(normalized)
    return tuple(texts)


def _first_int_after(value: str, start: int) -> int | None:
    match = re.search(r"\d[\d.,]*", value[start:])
    if not match:
        return None
    digits = re.sub(r"[^0-9]", "", match.group(0))
    return int(digits) if digits else None


def _iter_money_candidates(value: str) -> tuple[tuple[str, int], ...]:
    candidates = [
        (match.start(), match.end(), match.group(0))
        for match in MONEY_PATTERN.finditer(value)
    ]
    candidates.extend(
        (match.start(), match.end(), match.group(0))
        for match in LEADING_SYMBOL_MONEY_PATTERN.finditer(value)
    )
    ordered: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()
    for _start, end, text in sorted(candidates):
        key = (text, end)
        if key in seen:
            continue
        seen.add(key)
        ordered.append((text, end))
    return tuple(ordered)


def _is_plausible_buff_order_price(raw_value: str, value: Decimal) -> bool:
    if value <= 0:
        return False
    if re.search(r"\d[\d.,]*\s*(?:\u00a5|\uffe5)\s*$", raw_value):
        return False
    if re.search(r"(?:\u00a5|\uffe5)\s*\d{5,}\s*$", raw_value):
        return False
    return value <= 1_000_000


def _append_debug(debug_log: list[str] | None, message: str) -> None:
    if debug_log is not None:
        debug_log.append(message)

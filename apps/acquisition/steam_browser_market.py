"""Steam Market browser scraper with verbose diagnostics."""

from __future__ import annotations

import asyncio
import random
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
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
    parse_required_market_decimal,
    quality_from_market_hash,
    variant_key,
)

STEAM_LISTING_URL = "https://steamcommunity.com/market/listings/730/{market_hash_name}"
MONEY_PATTERN = re.compile(
    r"(?:CNY|USD|EUR|GBP|\$|\u20ac|\u00a3|\u00a5|\uffe5)\s*\d[\d.,]*"
    r"|\d[\d.,]*\s*(?:CNY|USD|EUR|GBP|\u20ac|\u00a3|\u00a5|\uffe5)",
    re.IGNORECASE,
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
    ) -> None:
        self._config = config or SteamBrowserConnectorConfig()
        self._log = log

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
                candidate: SteamBrowserCandidate,
            ) -> SteamBrowserObservation | SteamBrowserCandidateError:
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
                        return SteamBrowserCandidateError(
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
        url = candidate.steam_url or STEAM_LISTING_URL.format(
            market_hash_name=quote(candidate.market_hash_name)
        )
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
            payload = await page.evaluate(
                f"""
                () => ({{
                  url: location.href,
                  title: document.title,
                  bodyText: document.body ? document.body.innerText : "",
                  selectorTexts: {list(STEAM_PRICE_SELECTORS)!r}.flatMap((selector) =>
                    Array.from(document.querySelectorAll(selector)).map((el) => ({{
                      selector,
                      text: el.innerText
                    }}))
                  )
                }})
                """
            )
        finally:
            await page.close()

        title = str(payload.get("title") or "")
        body_text = str(payload.get("bodyText") or "")
        selector_texts = list(payload.get("selectorTexts") or [])
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

    def _debug(self, item: str, debug_log: list[str], message: str) -> None:
        debug_log.append(message)
        self._emit(item, message)

    def _emit(self, item: str, message: str) -> None:
        if self._log:
            self._log(f"[steam] {item}: {message}")


def extract_steam_price_text(
    selector_texts: list[Any],
    body_text: str,
    *,
    quality: str | None = None,
    stattrak: bool = False,
    debug_log: list[str] | None = None,
) -> str | None:
    """Extract the first visible Steam sell price from selector hits or page text."""

    if quality:
        quality_lower = quality.lower()
        for entry in selector_texts:
            text = str(entry.get("text") if isinstance(entry, dict) else entry)
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            if not lines or lines[0].lower() != quality_lower:
                continue
            prices = [str(price) for price in MONEY_PATTERN.findall(text)]
            if not prices:
                _append_debug(debug_log, f"quality card had no money text={text!r}")
                continue
            price_index = 1 if stattrak and len(prices) > 1 else 0
            _append_debug(
                debug_log,
                f"price matched quality card quality={quality!r} stattrak={stattrak}",
            )
            return prices[price_index]

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


def _find_volume_text(body_text: str) -> str | None:
    for line in body_text.splitlines():
        lowered = line.lower()
        if "volume" in lowered or "sold" in lowered:
            return line
    return None


def _append_debug(debug_log: list[str] | None, message: str) -> None:
    if debug_log is not None:
        debug_log.append(message)

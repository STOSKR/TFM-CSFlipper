"""Steam Market browser scraper with verbose diagnostics."""

from __future__ import annotations

import asyncio
import json
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
            payload = await page.evaluate(
                f"""
                () => ({{
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
                  )
                }})
                """
            )
        finally:
            await page.close()

        title = str(payload.get("title") or "")
        body_text = str(payload.get("bodyText") or "")
        ssr_loader_data = list(payload.get("ssrLoaderData") or [])
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

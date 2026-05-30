"""Steam Market acquisition connector."""

from __future__ import annotations

import asyncio
import random
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import httpx

from packages.contracts.observations import MarketObservationContract
from packages.domain.canonical_id import build_canonical_asset_id
from packages.domain.enums import SourceType

STEAM_PRICEOVERVIEW_URL = "https://steamcommunity.com/market/priceoverview/"
RETRIABLE_STATUSES = {429, 500, 502, 503, 504}
CURRENCY_CODES = {
    "1": "USD",
    "3": "EUR",
    "5": "GBP",
}


class SteamMarketError(RuntimeError):
    """Raised when Steam Market cannot return a usable observation."""


@dataclass(frozen=True, slots=True)
class SteamMarketCandidate:
    market_hash_name: str
    asset_name: str | None = None
    quality: str | None = None
    stattrak: bool = False
    category: str | None = None


@dataclass(frozen=True, slots=True)
class SteamMarketObservation:
    observation: MarketObservationContract
    asset_name: str
    category: str | None
    quality: str | None
    variant_key: str


@dataclass(frozen=True, slots=True)
class SteamMarketConnectorConfig:
    appid: int = 730
    currency: str = "3"
    country: str = "ES"
    timeout_seconds: float = 20.0
    retries: int = 3
    backoff_seconds: float = 0.75
    min_delay_seconds: float = 0.0
    max_delay_seconds: float = 0.0
    max_concurrency: int = 2


class SteamMarketConnector:
    """Async connector for Steam Market priceoverview snapshots."""

    def __init__(
        self,
        *,
        client: httpx.AsyncClient | None = None,
        config: SteamMarketConnectorConfig | None = None,
    ) -> None:
        self._client = client
        self._owns_client = client is None
        self._config = config or SteamMarketConnectorConfig()

    async def __aenter__(self) -> SteamMarketConnector:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._config.timeout_seconds)
        return self

    async def __aexit__(self, *_exc_info: object) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()

    async def fetch_price_overview(
        self,
        candidate: SteamMarketCandidate,
        *,
        correlation_id: str,
    ) -> SteamMarketObservation:
        await self._sleep_between_requests()
        payload = await self._request_priceoverview(candidate.market_hash_name)
        if not payload.get("success"):
            raise SteamMarketError(
                f"Steam returned unsuccessful payload for {candidate.market_hash_name}"
            )

        price_text = str(payload.get("median_price") or payload.get("lowest_price") or "").strip()
        if not price_text:
            raise SteamMarketError(
                f"Steam payload does not include price for {candidate.market_hash_name}"
            )

        asset_name = candidate.asset_name or _asset_name_from_market_hash(
            candidate.market_hash_name
        )
        quality = candidate.quality or _quality_from_market_hash(candidate.market_hash_name)
        stattrak = candidate.stattrak or candidate.market_hash_name.lower().startswith("stattrak")
        asset_id = build_canonical_asset_id(name=asset_name, quality=quality, stattrak=stattrak)
        volume = _parse_volume(payload.get("volume"))
        currency = _currency_code(price_text, self._config.currency)
        observation = MarketObservationContract(
            correlation_id=correlation_id,
            asset_id=asset_id,
            platform_id="steam",
            observed_at=datetime.now(tz=UTC),
            price=_parse_price(price_text),
            currency=currency,
            source_type=SourceType.SCRAPING,
            volume=volume,
            source_reference=candidate.market_hash_name,
            raw_payload=dict(payload),
        )
        return SteamMarketObservation(
            observation=observation,
            asset_name=asset_name,
            category=candidate.category,
            quality=quality,
            variant_key=_variant_key(quality, stattrak),
        )

    async def fetch_candidates(
        self,
        candidates: list[SteamMarketCandidate],
        *,
        correlation_id: str,
    ) -> tuple[SteamMarketObservation, ...]:
        semaphore = asyncio.Semaphore(self._config.max_concurrency)

        async def fetch_one(candidate: SteamMarketCandidate) -> SteamMarketObservation:
            async with semaphore:
                return await self.fetch_price_overview(candidate, correlation_id=correlation_id)

        return tuple(await asyncio.gather(*(fetch_one(candidate) for candidate in candidates)))

    async def _request_priceoverview(self, market_hash_name: str) -> dict[str, Any]:
        if self._client is None:
            raise RuntimeError("SteamMarketConnector must be used as an async context manager")

        last_error: Exception | None = None
        for attempt in range(1, self._config.retries + 1):
            try:
                response = await self._client.get(
                    STEAM_PRICEOVERVIEW_URL,
                    params={
                        "appid": self._config.appid,
                        "currency": self._config.currency,
                        "country": self._config.country,
                        "market_hash_name": market_hash_name,
                    },
                    headers={
                        "Accept": "application/json",
                        "User-Agent": "TFM-CSFlipper/0.1 research simulation",
                    },
                )
                if response.status_code in RETRIABLE_STATUSES and attempt < self._config.retries:
                    await asyncio.sleep(self._config.backoff_seconds * attempt)
                    continue
                response.raise_for_status()
                return dict(response.json())
            except (httpx.HTTPError, ValueError) as exc:
                last_error = exc
                if attempt >= self._config.retries:
                    break
                await asyncio.sleep(self._config.backoff_seconds * attempt)
        raise SteamMarketError(f"Steam request failed for {market_hash_name}") from last_error

    async def _sleep_between_requests(self) -> None:
        if self._config.max_delay_seconds <= 0:
            return
        delay = random.uniform(
            max(0.0, self._config.min_delay_seconds),
            max(self._config.min_delay_seconds, self._config.max_delay_seconds),
        )
        await asyncio.sleep(delay)


def _parse_price(value: str) -> Decimal:
    cleaned = re.sub(r"[^0-9,.-]", "", value)
    if "," in cleaned and "." in cleaned:
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif "," in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    return Decimal(cleaned)


def _parse_volume(value: Any) -> int | None:
    if value is None:
        return None
    digits = re.sub(r"[^0-9]", "", str(value))
    return int(digits) if digits else None


def _currency_code(price_text: str, configured_currency: str) -> str:
    lowered = price_text.lower()
    if "€" in lowered or "eur" in lowered:
        return "EUR"
    if "$" in lowered or "usd" in lowered:
        return "USD"
    if "£" in lowered or "gbp" in lowered:
        return "GBP"
    return CURRENCY_CODES.get(configured_currency, "EUR")


def _asset_name_from_market_hash(value: str) -> str:
    return re.sub(r"\s*\([^)]+\)\s*$", "", value).strip()


def _quality_from_market_hash(value: str) -> str | None:
    match = re.search(r"\(([^)]+)\)\s*$", value)
    return match.group(1).strip() if match else None


def _variant_key(quality: str | None, stattrak: bool) -> str:
    quality_key = (quality or "default").strip().lower().replace(" ", "_")
    return f"{quality_key}_st{int(stattrak)}"

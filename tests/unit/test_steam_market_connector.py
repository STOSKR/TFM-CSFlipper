from decimal import Decimal

import httpx
import pytest

from apps.acquisition.steam_market import (
    STEAM_PRICEOVERVIEW_URL,
    SteamMarketCandidate,
    SteamMarketConnector,
    SteamMarketConnectorConfig,
    SteamMarketError,
)
from packages.domain.enums import SourceType


@pytest.mark.asyncio
async def test_steam_market_connector_normalizes_priceoverview() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url).startswith(STEAM_PRICEOVERVIEW_URL)
        assert request.url.params["market_hash_name"] == "AK-47 | Slate (Field-Tested)"
        return httpx.Response(
            200,
            json={
                "success": True,
                "lowest_price": "12,34€",
                "median_price": "12,50€",
                "volume": "1,234",
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        connector = SteamMarketConnector(
            client=client,
            config=SteamMarketConnectorConfig(min_delay_seconds=0, max_delay_seconds=0),
        )
        result = await connector.fetch_price_overview(
            SteamMarketCandidate(market_hash_name="AK-47 | Slate (Field-Tested)"),
            correlation_id="corr-1",
        )

    assert result.observation.asset_id == "ak_47_slate__field_tested"
    assert result.observation.platform_id == "steam"
    assert result.observation.source_type == SourceType.SCRAPING
    assert result.observation.price == Decimal("12.50")
    assert result.observation.currency == "EUR"
    assert result.observation.volume == 1234


@pytest.mark.asyncio
async def test_steam_market_connector_retries_retriable_status() -> None:
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, json={"success": False})
        return httpx.Response(200, json={"success": True, "lowest_price": "$1.23"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        connector = SteamMarketConnector(
            client=client,
            config=SteamMarketConnectorConfig(
                retries=2,
                backoff_seconds=0,
                min_delay_seconds=0,
                max_delay_seconds=0,
            ),
        )
        result = await connector.fetch_price_overview(
            SteamMarketCandidate(market_hash_name="AK-47 | Slate"),
            correlation_id="corr-1",
        )

    assert calls == 2
    assert result.observation.price == Decimal("1.23")
    assert result.observation.currency == "USD"


@pytest.mark.asyncio
async def test_steam_market_connector_rejects_unsuccessful_payload() -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _request: httpx.Response(200, json={"success": False}))
    ) as client:
        connector = SteamMarketConnector(client=client)
        with pytest.raises(SteamMarketError):
            await connector.fetch_price_overview(
                SteamMarketCandidate(market_hash_name="AK-47 | Slate"),
                correlation_id="corr-1",
            )

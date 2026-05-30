"""CLI command for Steam Market priceoverview acquisition."""

from __future__ import annotations

import argparse
import asyncio
from uuid import uuid4

from apps.acquisition.steam_market import SteamMarketCandidate, SteamMarketConnector
from packages.persistence.connection import create_pool
from packages.persistence.repositories import MarketObservationIngestionRepository


async def scrape_market_hash_name(market_hash_name: str, *, dry_run: bool) -> int:
    correlation_id = f"steam:{uuid4()}"
    async with SteamMarketConnector() as connector:
        result = await connector.fetch_price_overview(
            SteamMarketCandidate(market_hash_name=market_hash_name),
            correlation_id=correlation_id,
        )

    if dry_run:
        print(result.observation.model_dump_json())
        return 1

    pool = await create_pool(max_size=2)
    try:
        async with pool.acquire() as connection:
            await MarketObservationIngestionRepository(connection).record_observation(
                result.observation,
                asset_name=result.asset_name,
                category=result.category,
                quality=result.quality,
                variant_key=result.variant_key,
            )
    finally:
        await pool.close()

    print("imported_observations=1")
    return 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape one Steam Market priceoverview snapshot.")
    parser.add_argument("market_hash_name", help="Steam market_hash_name to scrape")
    parser.add_argument("--dry-run", action="store_true", help="Print normalized observation only")
    args = parser.parse_args()

    asyncio.run(scrape_market_hash_name(args.market_hash_name, dry_run=args.dry_run))


if __name__ == "__main__":
    main()

"""Short wrapper for Steam Market price acquisition.

Examples:
    python steam_market.py "AK-47 | Redline (Field-Tested)" --dry-run
    python steam_market.py --candidates selected.json --output steam_observations.json --dry-run
    python steam_market.py --candidates selected.json --persist
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from apps.acquisition.steam_market import SteamMarketCandidate, SteamMarketConnector
from packages.persistence.connection import create_pool
from packages.persistence.repositories import MarketObservationIngestionRepository


async def run(args: argparse.Namespace) -> int:
    candidates = _load_candidates(args)
    correlation_id = f"steam:{uuid4()}"

    async with SteamMarketConnector() as connector:
        observations = await connector.fetch_candidates(
            candidates,
            correlation_id=correlation_id,
        )

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(
                [observation.observation.model_dump(mode="json") for observation in observations],
                indent=2,
            ),
            encoding="utf-8",
        )

    if not args.persist:
        for observation in observations:
            print(observation.observation.model_dump_json())
        print(f"steam_price_observations={len(observations)}")
        return len(observations)

    pool = await create_pool(max_size=2)
    try:
        async with pool.acquire() as connection:
            repository = MarketObservationIngestionRepository(connection)
            for observation in observations:
                await repository.record_observation(
                    observation.observation,
                    asset_name=observation.asset_name,
                    category=observation.category,
                    quality=observation.quality,
                    variant_key=observation.variant_key,
                )
    finally:
        await pool.close()

    print(f"imported_steam_price_observations={len(observations)}")
    return len(observations)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch Steam Market price snapshots.")
    parser.add_argument("market_hash_name", nargs="?", help="One Steam market_hash_name")
    parser.add_argument("--candidates", type=Path, help="SteamDT candidate JSON file")
    parser.add_argument("--output", type=Path, help="Where to write normalized observations")
    parser.add_argument("--persist", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.dry_run:
        args.persist = False

    asyncio.run(run(args))


def _load_candidates(args: argparse.Namespace) -> list[SteamMarketCandidate]:
    if args.candidates:
        rows = _load_rows(args.candidates)
        return [
            SteamMarketCandidate(
                market_hash_name=str(row["market_hash_name"]),
                asset_name=str(row.get("item_name") or row.get("asset_name") or "")
                or None,
                quality=str(row.get("quality") or "") or None,
                stattrak=bool(row.get("stattrak", False)),
            )
            for row in rows
            if row.get("market_hash_name")
        ]

    if args.market_hash_name:
        return [SteamMarketCandidate(market_hash_name=args.market_hash_name)]

    raise ValueError("provide market_hash_name or --candidates")


def _load_rows(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, list):
        raise ValueError("candidate JSON must be a list")
    return [row for row in payload if isinstance(row, dict)]


if __name__ == "__main__":
    main()

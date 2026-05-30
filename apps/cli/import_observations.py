"""CLI command for manual CSV/JSON observation imports."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from apps.acquisition.manual_import import load_manual_observations
from packages.persistence.connection import create_pool
from packages.persistence.repositories import MarketObservationIngestionRepository


async def import_file(path: Path, *, dry_run: bool) -> int:
    records = load_manual_observations(path)
    if dry_run:
        print(f"validated_observations={len(records)}")
        return len(records)

    pool = await create_pool(max_size=2)
    try:
        async with pool.acquire() as connection:
            repository = MarketObservationIngestionRepository(connection)
            for record in records:
                await repository.record_observation(
                    record.observation,
                    asset_name=record.asset_name,
                    category=record.category,
                    quality=record.quality,
                    variant_key=record.variant_key,
                )
    finally:
        await pool.close()

    print(f"imported_observations={len(records)}")
    return len(records)


def main() -> None:
    parser = argparse.ArgumentParser(description="Import manual market observations.")
    parser.add_argument("path", type=Path, help="CSV or JSON file to import")
    parser.add_argument("--dry-run", action="store_true", help="Validate without persisting")
    args = parser.parse_args()

    asyncio.run(import_file(args.path, dry_run=args.dry_run))


if __name__ == "__main__":
    main()

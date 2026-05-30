"""CLI command for OCR market observation imports."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from apps.acquisition.ocr_import import load_ocr_observations
from packages.persistence.connection import create_pool
from packages.persistence.repositories import MarketObservationIngestionRepository


async def import_ocr_file(
    path: Path,
    *,
    dry_run: bool,
    persist: bool,
    min_confidence: float,
) -> int:
    records = await load_ocr_observations(path, min_confidence=min_confidence)
    if dry_run or not persist:
        for record in records:
            print(record.observation.model_dump_json())
        print(f"ocr_observations={len(records)}")
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

    print(f"imported_ocr_observations={len(records)}")
    return len(records)


def main() -> None:
    parser = argparse.ArgumentParser(description="Import OCR market observations.")
    parser.add_argument("path", type=Path, help="Image capture or .txt OCR fixture")
    parser.add_argument("--min-confidence", type=float, default=0.5)
    parser.add_argument("--persist", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    asyncio.run(
        import_ocr_file(
            args.path,
            dry_run=args.dry_run,
            persist=args.persist,
            min_confidence=args.min_confidence,
        )
    )


if __name__ == "__main__":
    main()

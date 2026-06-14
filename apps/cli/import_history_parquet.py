"""Inspect and import historical parquet price data into market history tables."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from packages.datasets.historical_parquet import (
    inspect_direction_parquet,
    iter_snapshots_from_direction_parquet,
)
from packages.persistence.connection import create_pool
from packages.persistence.simple_market import (
    SimpleMarketSnapshot,
    SimpleMarketSnapshotRepository,
)


async def run(args: argparse.Namespace) -> int:
    report = inspect_direction_parquet(args.input)
    print(f"parquet_file={report.path}")
    print(f"rows={report.rows}")
    print(f"variants={report.variants}")
    print(f"date_column={report.date_column or '-'}")
    min_observed_at = report.min_observed_at.isoformat() if report.min_observed_at else "-"
    max_observed_at = report.max_observed_at.isoformat() if report.max_observed_at else "-"
    print(f"min_observed_at={min_observed_at}")
    print(f"max_observed_at={max_observed_at}")
    if report.missing_columns:
        print(f"missing_columns={','.join(report.missing_columns)}")
        return 2

    snapshots = iter_snapshots_from_direction_parquet(
        args.input,
        currency=args.currency,
        limit_variants=args.limit_variants,
    )

    if not args.persist:
        snapshots_ready = 0
        history_points_ready = 0
        sample: SimpleMarketSnapshot | None = None
        for snapshot in snapshots:
            sample = sample or snapshot
            snapshots_ready += 1
            history_points_ready += len(snapshot.steam_recent_sales)
        print(f"snapshots_ready={snapshots_ready}")
        print(f"history_points_ready={history_points_ready}")
        _print_sample(sample)
        print("mode=dry_run")
        return 0

    pool = await create_pool(max_size=2)
    persisted = 0
    history_points_persisted = 0
    sample = None
    try:
        async with pool.acquire() as connection:
            repository = SimpleMarketSnapshotRepository(connection)
            batch: list[SimpleMarketSnapshot] = []
            for snapshot in snapshots:
                sample = sample or snapshot
                history_points_persisted += len(snapshot.steam_recent_sales)
                batch.append(snapshot)
                if len(batch) >= args.batch_size:
                    persisted += await repository.record_snapshots(tuple(batch))
                    print(
                        f"progress snapshots={persisted} "
                        f"history_points={history_points_persisted}"
                    )
                    batch.clear()
            if batch:
                persisted += await repository.record_snapshots(tuple(batch))
    finally:
        await pool.close()

    _print_sample(sample)
    print(f"mode=persisted snapshots={persisted} history_points={history_points_persisted}")
    return persisted


def _print_sample(sample: SimpleMarketSnapshot | None) -> None:
    if sample is None:
        return
    print(
        "sample_item="
        f"{sample.representation_name} "
        f"steam_points={len(sample.steam_recent_sales)} "
        f"latest_price={sample.steam_price} {sample.steam_currency}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import historical parquet data into market_items and market_history_points."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/direction_dataset_model_sample.parquet"),
    )
    parser.add_argument("--currency", default="EUR")
    parser.add_argument("--limit-variants", type=int)
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument("--persist", action="store_true")
    args = parser.parse_args()

    asyncio.run(run(args))


if __name__ == "__main__":
    main()

"""Create a verified local Parquet copy of the existing Supabase history."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
from typing import Any

from packages.datasets.history_archive import (
    default_history_backup_dir,
    write_history_archive_records,
)
from packages.persistence.connection import create_pool


async def run(args: argparse.Namespace) -> int:
    pool = await create_pool(max_size=1)
    exported_rows = 0
    files = 0
    backups = 0
    try:
        async with pool.acquire() as connection:
            async with connection.transaction():
                cursor = connection.cursor(
                    """
                    select
                        h.item_id::text as item_id,
                        i.representation_name,
                        i.name,
                        i.quality,
                        i.stattrak,
                        h.observed_at,
                        h.platform_id,
                        h.metric_name,
                        h.metric_value,
                        h.currency,
                        h.price_eur,
                        h.price_cny,
                        h.raw_payload,
                        h.updated_at as archived_at
                    from market_history_points h
                    join market_items i on i.id = h.item_id
                    order by h.observed_at, h.item_id, h.platform_id, h.metric_name
                    """,
                    prefetch=args.batch_size,
                )
                batch: list[dict[str, Any]] = []
                async for row in cursor:
                    batch.append({**dict(row), "archive_source": "supabase_export"})
                    if len(batch) >= args.batch_size:
                        report = write_history_archive_records(
                            batch,
                            archive_dir=args.archive_dir,
                            backup_dir=args.archive_backup_dir,
                        )
                        exported_rows += report.rows
                        files += len(report.files)
                        backups += len(report.backup_files)
                        print(f"archive_progress rows={exported_rows} files={files}", flush=True)
                        batch.clear()
                if batch:
                    report = write_history_archive_records(
                        batch,
                        archive_dir=args.archive_dir,
                        backup_dir=args.archive_backup_dir,
                    )
                    exported_rows += report.rows
                    files += len(report.files)
                    backups += len(report.backup_files)
    finally:
        await pool.close()
    print(f"archive_exported_rows={exported_rows}")
    print(f"archive_files={files}")
    print(f"archive_backup_files={backups}")
    print(f"archive_dir={args.archive_dir}")
    if args.archive_backup_dir is not None:
        print(f"archive_backup_dir={args.archive_backup_dir}")
    return exported_rows


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export Supabase market history to content-addressed Parquet archive parts."
    )
    parser.add_argument("--archive-dir", type=Path, default=Path("data/history/market_history_v1"))
    parser.add_argument("--archive-backup-dir", type=Path, default=default_history_backup_dir())
    parser.add_argument("--batch-size", type=int, default=50_000)
    args = parser.parse_args()
    if args.batch_size <= 0:
        parser.error("--batch-size must be positive")
    asyncio.run(run(args))


if __name__ == "__main__":
    main()

"""Export Supabase state into the static web dashboard JSON."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import cast

from packages.persistence.connection import create_pool
from packages.runtime_config import load_runtime_config
from packages.web import build_dashboard_payload, market_items_query


async def run(args: argparse.Namespace) -> Path:
    runtime_config = load_runtime_config()
    output_path = cast(Path, args.output)
    pool = await create_pool(max_size=2)
    try:
        async with pool.acquire() as connection:
            rows = await connection.fetch(market_items_query(), args.limit)
    finally:
        await pool.close()

    payload = build_dashboard_payload(
        tuple(dict(row) for row in rows),
        risk_config=runtime_config.risk,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"dashboard_items={len(payload['recommendations'])}")
    print(f"output_file={output_path}")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Export dashboard JSON for apps/web.")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("apps/web/data/dashboard.json"),
    )
    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()

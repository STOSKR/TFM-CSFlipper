"""Build a supervised trading dataset from Supabase market history."""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pandas as pd  # type: ignore[import-untyped]

from packages.datasets.trading import TradingDatasetBuildConfig, build_trading_dataset_from_history
from packages.persistence.connection import create_pool
from packages.runtime_config import load_runtime_config


async def run(args: argparse.Namespace) -> int:
    runtime_config = load_runtime_config(args.config)
    cny_per_eur = Decimal(str(args.cny_per_eur))
    steam_sale_factor = Decimal("1") - runtime_config.fees.steam_sale_rate
    steam_cashout_loss = runtime_config.fees.withdrawal_rate
    if args.input_parquet:
        history = pd.read_parquet(args.input_parquet)
    else:
        history = await _fetch_history(args)

    metadata = build_trading_dataset_from_history(
        history,
        config=TradingDatasetBuildConfig(
            output_dir=args.output,
            trade_direction=args.trade_direction,
            horizon_days=args.horizon_days,
            future_tolerance_days=args.future_tolerance_days,
            min_profit_eur=Decimal(str(args.min_profit_eur)),
            min_return=Decimal(str(args.min_return)),
            cny_per_eur=cny_per_eur,
            steam_sale_factor=steam_sale_factor,
            buff_sale_factor=Decimal(str(args.buff_sale_factor)),
            steam_cashout_loss=steam_cashout_loss,
            start_date=args.start_date,
            validation_start=args.validation_start,
            test_start=args.test_start,
            test_end=args.test_end,
            purge_gap_days=args.purge_gap_days,
        ),
    )
    print(f"dataset_dir={metadata['output_dir']}")
    print(f"rows_included={metadata['rows_included']}")
    print(f"horizon_days={metadata['horizon_days']}")
    print(f"future_tolerance_days={metadata['future_tolerance_days']}")
    print(f"purge_gap_days={metadata['purge_gap_days']}")
    print(f"trade_direction={metadata['trade_direction']}")
    print(f"target={metadata['target_column']}")
    print(f"steam_sale_factor={metadata['steam_sale_factor']}")
    print(f"buff_sale_factor={metadata['buff_sale_factor']}")
    print(f"steam_cashout_loss={metadata['steam_cashout_loss']}")
    for split_name, split in metadata["splits"].items():
        print(
            f"split={split_name} rows={split['rows']} items={split['items']} "
            f"target_rate={split['target_rate']} "
            f"min_date={split['min_date']} max_date={split['max_date']}"
        )
    print("metadata=metadata.json")
    return 0


async def _fetch_history(args: argparse.Namespace) -> pd.DataFrame:
    pool = await create_pool(max_size=2)
    try:
        async with pool.acquire() as connection:
            rows = await connection.fetch(
                """
                select
                    i.id::text as item_id,
                    i.representation_name,
                    i.name,
                    i.quality,
                    i.stattrak,
                    h.observed_at,
                    h.platform_id,
                    h.metric_name,
                    h.metric_value,
                    h.price_eur,
                    h.price_cny
                from market_history_points h
                join market_items i on i.id = h.item_id
                where h.metric_name in (
                    'sell_price',
                    'buy_order_price',
                    'sales_count',
                    'listing_count'
                )
                  and ($1::timestamptz is null or h.observed_at >= $1::timestamptz)
                order by i.id, h.observed_at, h.platform_id, h.metric_name
                limit $2
                """,
                args.query_start,
                args.limit_rows,
            )
    finally:
        await pool.close()
    return pd.DataFrame([dict(row) for row in rows])


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build trading train/validation/test parquet splits from market history."
    )
    parser.add_argument("--config", type=Path, default=Path("csflipper_config.toml"))
    parser.add_argument("--input-parquet", type=Path)
    parser.add_argument("--output", type=Path, default=Path("data/datasets/trading_profit_v1"))
    parser.add_argument(
        "--trade-direction",
        choices=("buff_to_steam_sell", "steam_to_buff_buy_order"),
        default="steam_to_buff_buy_order",
    )
    parser.add_argument("--horizon-days", type=int, default=8)
    parser.add_argument("--future-tolerance-days", type=int, default=7)
    parser.add_argument(
        "--purge-gap-days",
        type=int,
        default=0,
        help="Days excluded before each split boundary to prevent outcome overlap.",
    )
    parser.add_argument("--min-profit-eur", type=str, default="0")
    parser.add_argument("--min-return", type=str, default="0")
    parser.add_argument("--cny-per-eur", type=str, default="8")
    parser.add_argument("--buff-sale-factor", type=str, default="0.975")
    parser.add_argument("--start-date", type=_date_arg)
    parser.add_argument("--validation-start", type=_date_arg, default=datetime(2026, 1, 1))
    parser.add_argument("--test-start", type=_date_arg, default=datetime(2026, 3, 1))
    parser.add_argument(
        "--test-end",
        type=_date_arg,
        help="Exclusive end date for a bounded test window.",
    )
    parser.add_argument("--query-start", type=_date_arg)
    parser.add_argument("--limit-rows", type=int, default=None)
    args = parser.parse_args()
    raise SystemExit(asyncio.run(run(args)))


def _date_arg(value: str) -> datetime:
    return datetime.fromisoformat(value)


if __name__ == "__main__":
    main()

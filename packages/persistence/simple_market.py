"""Persistence for the simplified phase-1 market snapshot schema."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any

import asyncpg

JsonRows = Sequence[Mapping[str, Any]]


@dataclass(frozen=True, slots=True)
class SimpleMarketSnapshot:
    name: str
    quality: str
    stattrak: bool
    scraped_at: datetime
    steam_url: str | None = None
    buff_url: str | None = None
    steam_price: Decimal | None = None
    steam_currency: str | None = None
    steam_recent_sales: JsonRows = field(default_factory=tuple)
    steam_buy_orders: JsonRows = field(default_factory=tuple)
    buff_price: Decimal | None = None
    buff_currency: str | None = None
    buff_recent_sales: JsonRows = field(default_factory=tuple)
    buff_buy_orders: JsonRows = field(default_factory=tuple)
    source_strategies: JsonRows = field(default_factory=tuple)


@dataclass(slots=True)
class SimpleMarketSnapshotRepository:
    connection: asyncpg.Connection

    async def record_snapshot(self, snapshot: SimpleMarketSnapshot) -> None:
        async with self.connection.transaction():
            await self.upsert_item(snapshot)
            await self.upsert_snapshot(snapshot)

    async def record_snapshots(self, snapshots: Sequence[SimpleMarketSnapshot]) -> int:
        for snapshot in snapshots:
            await self.record_snapshot(snapshot)
        return len(snapshots)

    async def upsert_item(self, snapshot: SimpleMarketSnapshot) -> None:
        await self.connection.execute(
            """
            insert into market_items (
                name,
                quality,
                stattrak,
                steam_url,
                buff_url
            )
            values ($1, $2, $3, $4, $5)
            on conflict (name, quality, stattrak) do update set
                steam_url = coalesce(excluded.steam_url, market_items.steam_url),
                buff_url = coalesce(excluded.buff_url, market_items.buff_url),
                updated_at = now()
            """,
            _required_text(snapshot.name, "name"),
            _required_text(snapshot.quality, "quality"),
            snapshot.stattrak,
            snapshot.steam_url,
            snapshot.buff_url,
        )

    async def upsert_snapshot(self, snapshot: SimpleMarketSnapshot) -> None:
        await self.connection.execute(
            """
            insert into market_snapshots (
                name,
                quality,
                stattrak,
                scraped_at,
                steam_price,
                steam_currency,
                steam_recent_sales,
                steam_buy_orders,
                buff_price,
                buff_currency,
                buff_recent_sales,
                buff_buy_orders
            )
            values (
                $1, $2, $3, $4, $5, $6, $7::jsonb, $8::jsonb,
                $9, $10, $11::jsonb, $12::jsonb
            )
            on conflict (name, quality, stattrak, scraped_at) do update set
                steam_price = excluded.steam_price,
                steam_currency = excluded.steam_currency,
                steam_recent_sales = excluded.steam_recent_sales,
                steam_buy_orders = excluded.steam_buy_orders,
                buff_price = excluded.buff_price,
                buff_currency = excluded.buff_currency,
                buff_recent_sales = excluded.buff_recent_sales,
                buff_buy_orders = excluded.buff_buy_orders
            """,
            _required_text(snapshot.name, "name"),
            _required_text(snapshot.quality, "quality"),
            snapshot.stattrak,
            snapshot.scraped_at,
            snapshot.steam_price,
            _currency(snapshot.steam_currency),
            _jsonb(snapshot.steam_recent_sales),
            _jsonb(snapshot.steam_buy_orders),
            snapshot.buff_price,
            _currency(snapshot.buff_currency),
            _jsonb(snapshot.buff_recent_sales),
            _jsonb(snapshot.buff_buy_orders),
        )


def _required_text(value: str, field_name: str) -> str:
    text = value.strip()
    if not text:
        raise ValueError(f"{field_name} cannot be empty")
    return text


def _currency(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip().upper()
    return text or None


def _jsonb(value: JsonRows) -> str:
    return json.dumps([dict(row) for row in value], default=str)

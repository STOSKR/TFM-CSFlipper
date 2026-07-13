"""Persistence for the simplified phase-1 market snapshot schema."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

import asyncpg

from packages.domain.market_parsing import parse_market_decimal

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
    buff_price_history: JsonRows = field(default_factory=tuple)
    source_strategies: JsonRows = field(default_factory=tuple)

    @property
    def representation_name(self) -> str:
        return representation_name(self.name, self.quality, self.stattrak)


@dataclass(frozen=True, slots=True)
class SnapshotPersistenceReport:
    snapshots: int
    history_points: int


@dataclass(slots=True)
class SimpleMarketSnapshotRepository:
    connection: asyncpg.Connection

    async def record_snapshot(self, snapshot: SimpleMarketSnapshot) -> int:
        async with self.connection.transaction():
            item_id = await self.upsert_item(snapshot)
            return await self.upsert_history_points(snapshot, item_id=item_id)

    async def record_snapshots(self, snapshots: Sequence[SimpleMarketSnapshot]) -> int:
        await self.record_snapshots_report(snapshots)
        return len(snapshots)

    async def record_snapshots_report(
        self,
        snapshots: Sequence[SimpleMarketSnapshot],
    ) -> SnapshotPersistenceReport:
        history_points = 0
        for snapshot in snapshots:
            history_points += await self.record_snapshot(snapshot)
        return SnapshotPersistenceReport(
            snapshots=len(snapshots),
            history_points=history_points,
        )

    async def upsert_item(self, snapshot: SimpleMarketSnapshot) -> UUID:
        row = await self.connection.fetchrow(
            """
            with latest_eur_cny as (
                select rate as cny_per_eur
                from market_currency_rates
                where base_currency = 'EUR'
                  and quote_currency = 'CNY'
                order by effective_from desc
                limit 1
            )
            insert into market_items (
                name,
                quality,
                stattrak,
                representation_name,
                steam_url,
                buff_url,
                scraped_at,
                last_checked_at,
                steam_price,
                steam_currency,
                steam_price_eur,
                steam_price_cny,
                steam_buy_orders,
                buff_price,
                buff_currency,
                buff_price_eur,
                buff_price_cny,
                buff_buy_orders
            )
            select
                $1,
                $2,
                $3,
                $4,
                $5,
                $6,
                $7,
                $7,
                $8,
                $9,
                case
                    when $8::numeric is null or $9::char(3) is null then null
                    when upper($9::char(3)) = 'EUR' then $8::numeric
                    when upper($9::char(3)) = 'CNY' then $8::numeric / latest_eur_cny.cny_per_eur
                    else null
                end,
                case
                    when $8::numeric is null or $9::char(3) is null then null
                    when upper($9::char(3)) = 'CNY' then $8::numeric
                    when upper($9::char(3)) = 'EUR' then $8::numeric * latest_eur_cny.cny_per_eur
                    else null
                end,
                $10::jsonb,
                $11,
                $12,
                case
                    when $11::numeric is null or $12::char(3) is null then null
                    when upper($12::char(3)) = 'EUR' then $11::numeric
                    when upper($12::char(3)) = 'CNY' then $11::numeric / latest_eur_cny.cny_per_eur
                    else null
                end,
                case
                    when $11::numeric is null or $12::char(3) is null then null
                    when upper($12::char(3)) = 'CNY' then $11::numeric
                    when upper($12::char(3)) = 'EUR' then $11::numeric * latest_eur_cny.cny_per_eur
                    else null
                end,
                $13::jsonb
            from latest_eur_cny
            on conflict (name, quality, stattrak) do update set
                representation_name = excluded.representation_name,
                steam_url = coalesce(excluded.steam_url, market_items.steam_url),
                buff_url = coalesce(excluded.buff_url, market_items.buff_url),
                scraped_at = excluded.scraped_at,
                steam_price = coalesce(excluded.steam_price, market_items.steam_price),
                steam_currency = coalesce(excluded.steam_currency, market_items.steam_currency),
                steam_price_eur = coalesce(
                    excluded.steam_price_eur,
                    market_items.steam_price_eur
                ),
                steam_price_cny = coalesce(
                    excluded.steam_price_cny,
                    market_items.steam_price_cny
                ),
                steam_buy_orders = case
                    when excluded.steam_buy_orders = '[]'::jsonb
                    then market_items.steam_buy_orders
                    else excluded.steam_buy_orders
                end,
                buff_price = coalesce(excluded.buff_price, market_items.buff_price),
                buff_currency = coalesce(excluded.buff_currency, market_items.buff_currency),
                buff_price_eur = coalesce(
                    excluded.buff_price_eur,
                    market_items.buff_price_eur
                ),
                buff_price_cny = coalesce(
                    excluded.buff_price_cny,
                    market_items.buff_price_cny
                ),
                buff_buy_orders = case
                    when excluded.buff_buy_orders = '[]'::jsonb
                    then market_items.buff_buy_orders
                    else excluded.buff_buy_orders
                end,
                last_checked_at = greatest(
                    coalesce(market_items.last_checked_at, '-infinity'::timestamptz),
                    excluded.last_checked_at
                ),
                updated_at = case
                    when (
                        market_items.representation_name,
                        market_items.steam_url,
                        market_items.buff_url,
                        market_items.steam_price,
                        market_items.steam_currency,
                        market_items.steam_price_eur,
                        market_items.steam_price_cny,
                        market_items.steam_buy_orders,
                        market_items.buff_price,
                        market_items.buff_currency,
                        market_items.buff_price_eur,
                        market_items.buff_price_cny,
                        market_items.buff_buy_orders
                    ) is distinct from (
                        excluded.representation_name,
                        coalesce(excluded.steam_url, market_items.steam_url),
                        coalesce(excluded.buff_url, market_items.buff_url),
                        coalesce(excluded.steam_price, market_items.steam_price),
                        coalesce(excluded.steam_currency, market_items.steam_currency),
                        coalesce(excluded.steam_price_eur, market_items.steam_price_eur),
                        coalesce(excluded.steam_price_cny, market_items.steam_price_cny),
                        case
                            when excluded.steam_buy_orders = '[]'::jsonb
                            then market_items.steam_buy_orders
                            else excluded.steam_buy_orders
                        end,
                        coalesce(excluded.buff_price, market_items.buff_price),
                        coalesce(excluded.buff_currency, market_items.buff_currency),
                        coalesce(excluded.buff_price_eur, market_items.buff_price_eur),
                        coalesce(excluded.buff_price_cny, market_items.buff_price_cny),
                        case
                            when excluded.buff_buy_orders = '[]'::jsonb
                            then market_items.buff_buy_orders
                            else excluded.buff_buy_orders
                        end
                    )
                    then now()
                    else market_items.updated_at
                end
            returning id
            """,
            _required_text(snapshot.name, "name"),
            _required_text(snapshot.quality, "quality"),
            snapshot.stattrak,
            snapshot.representation_name,
            snapshot.steam_url,
            snapshot.buff_url,
            snapshot.scraped_at,
            snapshot.steam_price,
            _currency(snapshot.steam_currency),
            _jsonb(snapshot.steam_buy_orders),
            snapshot.buff_price,
            _currency(snapshot.buff_currency),
            _jsonb(snapshot.buff_buy_orders),
        )
        return UUID(str(row["id"]))

    async def upsert_history_points(
        self,
        snapshot: SimpleMarketSnapshot,
        *,
        item_id: UUID,
    ) -> int:
        rows = _history_points_from_snapshot(snapshot)
        if not rows:
            return 0

        await self.connection.executemany(
            """
            with latest_eur_cny as (
                select rate as cny_per_eur
                from market_currency_rates
                where base_currency = 'EUR'
                  and quote_currency = 'CNY'
                order by effective_from desc
                limit 1
            )
            insert into market_history_points (
                item_id,
                platform_id,
                observed_at,
                metric_name,
                metric_value,
                currency,
                price_eur,
                price_cny,
                raw_payload,
                updated_at
            )
            select
                $1,
                $2,
                $3,
                $4,
                $5,
                $6,
                case
                    when $4 not in ('sell_price', 'buy_order_price') then null
                    when $6::char(3) is null then null
                    when upper($6::char(3)) = 'EUR' then $5
                    when upper($6::char(3)) = 'CNY' then $5 / latest_eur_cny.cny_per_eur
                    else null
                end,
                case
                    when $4 not in ('sell_price', 'buy_order_price') then null
                    when $6::char(3) is null then null
                    when upper($6::char(3)) = 'CNY' then $5
                    when upper($6::char(3)) = 'EUR' then $5 * latest_eur_cny.cny_per_eur
                    else null
                end,
                $7::jsonb,
                now()
            from latest_eur_cny
            on conflict (item_id, platform_id, observed_at, metric_name) do update set
                metric_value = excluded.metric_value,
                currency = coalesce(
                    excluded.currency,
                    market_history_points.currency
                ),
                price_eur = excluded.price_eur,
                price_cny = excluded.price_cny,
                raw_payload = market_history_points.raw_payload || excluded.raw_payload,
                updated_at = now()
            where (
                market_history_points.metric_value,
                market_history_points.currency,
                market_history_points.price_eur,
                market_history_points.price_cny,
                market_history_points.raw_payload
            ) is distinct from (
                excluded.metric_value,
                coalesce(excluded.currency, market_history_points.currency),
                excluded.price_eur,
                excluded.price_cny,
                market_history_points.raw_payload || excluded.raw_payload
            )
            """,
            tuple(
                (
                    item_id,
                    row["platform_id"],
                    row["observed_at"],
                    row["metric_name"],
                    row["metric_value"],
                    row.get("currency"),
                    _json(row.get("raw_payload") or {}),
                )
                for row in rows
            ),
        )
        return len(rows)

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


def _json(value: Mapping[str, Any]) -> str:
    return json.dumps(dict(value), default=str)


def history_point_count(snapshot: SimpleMarketSnapshot) -> int:
    return len(_history_points_from_snapshot(snapshot))


def representation_name(name: str, quality: str, stattrak: bool) -> str:
    return f"{_required_text(name, 'name')}_{_quality_code(quality)}_{int(stattrak)}"


def _quality_code(value: str) -> str:
    text = _required_text(value, "quality")
    return {
        "Factory New": "FN",
        "Minimal Wear": "MW",
        "Field-Tested": "FT",
        "Well-Worn": "WW",
        "Battle-Scarred": "BS",
    }.get(text, text.upper().replace(" ", "_"))


def _history_points_from_snapshot(snapshot: SimpleMarketSnapshot) -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = []
    if snapshot.steam_price is not None:
        rows.append(
            {
                "platform_id": "steam",
                "observed_at": snapshot.scraped_at,
                "metric_name": "sell_price",
                "metric_value": snapshot.steam_price,
                "currency": _currency(snapshot.steam_currency),
                "raw_payload": {
                    "steam": {
                        "source": "steam_current_sell_price",
                        "price": str(snapshot.steam_price),
                    }
                },
            }
        )

    for row in snapshot.steam_recent_sales:
        observed_at = _history_observed_at(row)
        price = _decimal_value(row.get("price"))
        if observed_at is None or price is None:
            continue
        rows.append(
            {
                "platform_id": "steam",
                "observed_at": observed_at,
                "metric_name": "sell_price",
                "metric_value": price,
                "currency": _currency(snapshot.steam_currency),
                "raw_payload": {"steam": dict(row)},
            }
        )
        sales_count = _int_value(row.get("sales_count") or row.get("purchases"))
        if sales_count is not None:
            rows.append(
                {
                    "platform_id": "steam",
                    "observed_at": observed_at,
                    "metric_name": "sales_count",
                    "metric_value": Decimal(sales_count),
                    "raw_payload": {"steam": dict(row)},
                }
            )

    if snapshot.buff_price is not None:
        rows.append(
            {
                "platform_id": "buff",
                "observed_at": snapshot.scraped_at,
                "metric_name": "sell_price",
                "metric_value": snapshot.buff_price,
                "currency": _currency(snapshot.buff_currency),
                "raw_payload": {
                    "buff": {
                        "source": "buff_current_sell_price",
                        "price": str(snapshot.buff_price),
                    }
                },
            }
        )

    for row in snapshot.buff_price_history:
        observed_at = _history_observed_at(row)
        if observed_at is None:
            continue
        sell_price = _decimal_value(row.get("buff_sell_price"))
        buy_order_price = _decimal_value(row.get("buff_buy_order_price"))
        listing_count = _int_value(row.get("buff_listing_count"))
        if sell_price is None and buy_order_price is None and listing_count is None:
            continue
        currency = _currency(_optional_text(row.get("currency")) or snapshot.buff_currency)
        if sell_price is not None:
            rows.append(
                {
                    "platform_id": "buff",
                    "observed_at": observed_at,
                    "metric_name": "sell_price",
                    "metric_value": sell_price,
                    "currency": currency,
                    "raw_payload": {"buff": dict(row)},
                }
            )
        if buy_order_price is not None:
            rows.append(
                {
                    "platform_id": "buff",
                    "observed_at": observed_at,
                    "metric_name": "buy_order_price",
                    "metric_value": buy_order_price,
                    "currency": currency,
                    "raw_payload": {"buff": dict(row)},
                }
            )
        if listing_count is not None:
            rows.append(
                {
                    "platform_id": "buff",
                    "observed_at": observed_at,
                    "metric_name": "listing_count",
                    "metric_value": Decimal(listing_count),
                    "raw_payload": {"buff": dict(row)},
                }
            )

    return tuple(
        sorted(
            rows,
            key=lambda item: (
                item["observed_at"],
                item["platform_id"],
                item["metric_name"],
            ),
        )
    )


def _history_observed_at(row: Mapping[str, Any]) -> datetime | None:
    value = row.get("observed_at") or row.get("latest_observed_at")
    if isinstance(value, datetime):
        return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed.astimezone(UTC) if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    return None


def _decimal_value(value: object) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    return parse_market_decimal(str(value))


def _int_value(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def _optional_text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None

"""Integration checks against the current market persistence schema.

Each test opens an outer transaction and rolls it back.  The configured
database is therefore exercised without retaining fixtures or changing the
market history used by the application.
"""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import asyncpg
import pytest

from packages.persistence.connection import load_database_url, normalize_asyncpg_dsn
from packages.persistence.opportunity_signals import (
    MarketOpportunitySignal,
    MarketOpportunitySignalRepository,
)
from packages.persistence.simple_market import SimpleMarketSnapshot, SimpleMarketSnapshotRepository

REQUIRED_TABLES = (
    "market_currency_rates",
    "market_history_points",
    "market_items",
    "market_opportunity_signals",
)


async def _connect_migrated_database() -> asyncpg.Connection:
    """Connect only when the current public schema is available."""

    dsn = normalize_asyncpg_dsn(load_database_url())
    conn = await asyncpg.connect(dsn=dsn, ssl="require")
    missing = [
        table
        for table in REQUIRED_TABLES
        if await conn.fetchval("select to_regclass($1)", f"public.{table}") is None
    ]
    if missing:
        await conn.close()
        pytest.skip(f"current database schema is not migrated; missing: {', '.join(missing)}")
    return conn


@pytest.mark.asyncio
async def test_record_snapshot_persists_item_and_history_without_leaving_data() -> None:
    conn = await _connect_migrated_database()
    outer = conn.transaction()
    await outer.start()
    try:
        item_name = f"pytest-market-{uuid4().hex}"
        captured_at = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)
        snapshot = SimpleMarketSnapshot(
            name=item_name,
            quality="Field-Tested",
            stattrak=False,
            scraped_at=captured_at,
            steam_price=Decimal("20.00"),
            steam_currency="EUR",
            buff_price=Decimal("155.00"),
            buff_currency="CNY",
        )

        history_count = await SimpleMarketSnapshotRepository(conn).record_snapshot(snapshot)
        item = await conn.fetchrow(
            "select id, steam_price_eur, buff_price_cny from market_items "
            "where name = $1 and quality = $2 and stattrak = $3",
            item_name,
            "Field-Tested",
            False,
        )
        points = await conn.fetchval(
            "select count(*) from market_history_points where item_id = $1",
            item["id"],
        )

        assert history_count == 2
        assert item["steam_price_eur"] == Decimal("20.00")
        assert item["buff_price_cny"] == Decimal("155.00")
        assert points == 2
    finally:
        await outer.rollback()
        await conn.close()


@pytest.mark.asyncio
async def test_snapshot_upsert_keeps_one_item_and_refreshes_price() -> None:
    conn = await _connect_migrated_database()
    outer = conn.transaction()
    await outer.start()
    try:
        item_name = f"pytest-upsert-{uuid4().hex}"
        repository = SimpleMarketSnapshotRepository(conn)
        first = SimpleMarketSnapshot(
            name=item_name,
            quality="Minimal Wear",
            stattrak=True,
            scraped_at=datetime(2026, 8, 10, 12, 0, tzinfo=UTC),
            steam_price=Decimal("10.00"),
            steam_currency="EUR",
        )
        second = SimpleMarketSnapshot(
            name=item_name,
            quality="Minimal Wear",
            stattrak=True,
            scraped_at=datetime(2026, 8, 10, 13, 0, tzinfo=UTC),
            steam_price=Decimal("12.50"),
            steam_currency="EUR",
        )

        await repository.record_snapshot(first)
        await repository.record_snapshot(second)
        rows = await conn.fetch(
            "select steam_price, scraped_at from market_items "
            "where name = $1 and quality = $2 and stattrak = $3",
            item_name,
            "Minimal Wear",
            True,
        )

        assert len(rows) == 1
        assert rows[0]["steam_price"] == Decimal("12.50")
        assert rows[0]["scraped_at"] == second.scraped_at
    finally:
        await outer.rollback()
        await conn.close()


@pytest.mark.asyncio
async def test_record_signal_links_a_current_market_item() -> None:
    conn = await _connect_migrated_database()
    outer = conn.transaction()
    await outer.start()
    try:
        item_name = f"pytest-signal-{uuid4().hex}"
        snapshot = SimpleMarketSnapshot(
            name=item_name,
            quality="Factory New",
            stattrak=False,
            scraped_at=datetime(2026, 8, 10, 12, 0, tzinfo=UTC),
            steam_price=Decimal("30.00"),
            steam_currency="EUR",
        )
        await SimpleMarketSnapshotRepository(conn).record_snapshot(snapshot)
        item_id = await conn.fetchval(
            "select id from market_items where name = $1 and quality = $2 and stattrak = $3",
            item_name,
            "Factory New",
            False,
        )
        signal = MarketOpportunitySignal(
            item_id=item_id,
            model_name="pytest",
            model_version="integration",
            route_label="BUFF listing -> Steam listing",
            buy_platform="BUFF",
            buy_price_type="listing",
            sell_platform="STEAM",
            sell_price_type="listing",
            status="review",
            reason="integration transaction",
            data_quality_status="complete",
            expected_profit_eur=Decimal("2.50"),
            probability_profitable=Decimal("0.75"),
            is_signal=True,
        )

        inserted = await MarketOpportunitySignalRepository(conn).record_signals((signal,))
        stored = await conn.fetchrow(
            "select expected_profit_eur, is_signal from market_opportunity_signals "
            "where item_id = $1 and model_name = $2",
            item_id,
            "pytest",
        )

        assert inserted == 1
        assert stored["expected_profit_eur"] == Decimal("2.50")
        assert stored["is_signal"] is True
    finally:
        await outer.rollback()
        await conn.close()

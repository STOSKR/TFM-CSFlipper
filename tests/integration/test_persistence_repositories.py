from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import asyncpg
import pytest

from packages.contracts.observations import MarketObservationContract
from packages.domain.entities import Prediction
from packages.domain.enums import SourceType
from packages.persistence.connection import load_database_url, normalize_asyncpg_dsn
from packages.persistence.repositories import (
    MarketObservationIngestionRepository,
    OutboxRepository,
    PredictionIngestionRepository,
)

REQUIRED_TABLES = ("assets", "market_observations", "outbox_events", "predictions")


async def _connect_migrated_database() -> asyncpg.Connection:
    dsn = normalize_asyncpg_dsn(load_database_url())
    conn = await asyncpg.connect(dsn=dsn, ssl="require")
    missing = [
        table
        for table in REQUIRED_TABLES
        if await conn.fetchval("select to_regclass($1)", f"public.{table}") is None
    ]
    if missing:
        await conn.close()
        pytest.skip(f"database schema is not migrated; missing: {', '.join(missing)}")
    return conn


@pytest.mark.asyncio
async def test_record_observation_writes_observation_and_outbox_event() -> None:
    conn = await _connect_migrated_database()
    tx = conn.transaction()
    await tx.start()
    try:
        correlation_id = f"test-{uuid4()}"
        observation = MarketObservationContract(
            correlation_id=correlation_id,
            asset_id=f"pytest_asset_{uuid4().hex}",
            platform_id="manual",
            observed_at=datetime(2026, 5, 30, 12, 0, tzinfo=UTC),
            price=Decimal("10.50"),
            currency="EUR",
            source_type=SourceType.CSV,
            source_reference="pytest",
            raw_payload={"case": "integration"},
        )

        observation_id = await MarketObservationIngestionRepository(conn).record_observation(
            observation,
            asset_name="Pytest Asset",
            category="test",
            quality="Factory New",
        )

        observation_count = await conn.fetchval(
            "select count(*) from market_observations where id = $1",
            observation_id,
        )
        event_count = await conn.fetchval(
            """
            select count(*)
            from outbox_events
            where aggregate_id = $1
              and event_type = 'MarketObservationCaptured'
              and correlation_id = $2
            """,
            str(observation_id),
            correlation_id,
        )

        assert observation_count == 1
        assert event_count == 1
    finally:
        await tx.rollback()
        await conn.close()


@pytest.mark.asyncio
async def test_outbox_repository_fetches_and_marks_events() -> None:
    conn = await _connect_migrated_database()
    tx = conn.transaction()
    await tx.start()
    try:
        event_id = uuid4()
        await conn.execute(
            """
            insert into outbox_events (
                event_id,
                event_type,
                aggregate_id,
                payload,
                status,
                correlation_id
            )
            values ($1, 'PredictionRequested', 'pytest', '{}'::jsonb, 'pending', $2)
            """,
            event_id,
            f"test-{uuid4()}",
        )

        repository = OutboxRepository(conn)
        pending = await repository.fetch_pending(limit=10)
        assert any(event.event_id == event_id for event in pending)

        await repository.mark_processed(event_id)
        status = await conn.fetchval(
            "select status from outbox_events where event_id = $1",
            event_id,
        )
        assert status == "processed"
    finally:
        await tx.rollback()
        await conn.close()


@pytest.mark.asyncio
async def test_record_prediction_writes_prediction_and_outbox_event() -> None:
    conn = await _connect_migrated_database()
    tx = conn.transaction()
    await tx.start()
    try:
        correlation_id = f"test-{uuid4()}"
        prediction = Prediction(
            prediction_id=f"pred-{uuid4()}",
            asset_id=f"pytest_asset_{uuid4().hex}",
            platform_id="steam",
            probability_up=Decimal("0.65000"),
            expected_return=Decimal("0.12500000"),
            confidence=Decimal("0.70000"),
            prediction_horizon="7d",
            model_name="pytest-baseline",
            model_version="0.0.0",
            created_at=datetime(2026, 5, 30, 12, 0, tzinfo=UTC),
            correlation_id=correlation_id,
            features_snapshot={"momentum_7d": 0.12},
        )

        prediction_id = await PredictionIngestionRepository(conn).record_prediction(
            prediction,
            asset_name="Pytest Prediction Asset",
            category="test",
        )

        prediction_count = await conn.fetchval(
            "select count(*) from predictions where id = $1",
            prediction_id,
        )
        event_count = await conn.fetchval(
            """
            select count(*)
            from outbox_events
            where aggregate_id = $1
              and event_type = 'PredictionCompleted'
              and correlation_id = $2
            """,
            str(prediction_id),
            correlation_id,
        )

        assert prediction_count == 1
        assert event_count == 1
    finally:
        await tx.rollback()
        await conn.close()

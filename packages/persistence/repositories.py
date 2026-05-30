"""Async Postgres repositories for canonical market data and outbox events."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import asyncpg

from packages.contracts.events import DomainEventContract
from packages.contracts.observations import MarketObservationContract
from packages.domain.enums import DomainEventType, EventStatus

EventHandler = Callable[[DomainEventContract], Awaitable[None]]


@dataclass(slots=True)
class AssetRepository:
    connection: asyncpg.Connection

    async def upsert_asset(
        self,
        *,
        canonical_id: str,
        name: str,
        category: str | None = None,
        quality: str | None = None,
        rarity: str | None = None,
        stattrak: bool = False,
        souvenir: bool = False,
        external_identifiers: dict[str, str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> UUID:
        row = await self.connection.fetchrow(
            """
            insert into assets (
                canonical_id,
                name,
                category,
                quality,
                rarity,
                stattrak,
                souvenir,
                external_identifiers,
                metadata
            )
            values ($1, $2, $3, $4, $5, $6, $7, $8::jsonb, $9::jsonb)
            on conflict (canonical_id) do update set
                name = excluded.name,
                category = coalesce(excluded.category, assets.category),
                quality = coalesce(excluded.quality, assets.quality),
                rarity = coalesce(excluded.rarity, assets.rarity),
                external_identifiers = assets.external_identifiers || excluded.external_identifiers,
                metadata = assets.metadata || excluded.metadata,
                updated_at = now()
            returning id
            """,
            canonical_id,
            name,
            category,
            quality,
            rarity,
            stattrak,
            souvenir,
            _jsonb(external_identifiers or {}),
            _jsonb(metadata or {}),
        )
        return UUID(str(row["id"]))


@dataclass(slots=True)
class PlatformRepository:
    connection: asyncpg.Connection

    async def get_platform_id(self, code: str) -> UUID:
        row = await self.connection.fetchrow(
            "select id from platforms where code = $1",
            code,
        )
        if row is None:
            raise LookupError(f"platform not found: {code}")
        return UUID(str(row["id"]))


@dataclass(slots=True)
class MarketObservationRepository:
    connection: asyncpg.Connection

    async def insert_observation(
        self,
        observation: MarketObservationContract,
        *,
        asset_db_id: UUID,
        platform_db_id: UUID,
        variant_key: str = "default",
    ) -> UUID:
        row = await self.connection.fetchrow(
            """
            insert into market_observations (
                asset_id,
                platform_id,
                observed_at,
                price,
                currency,
                volume,
                liquidity_score,
                spread,
                float_value,
                variant_key,
                source_type,
                source_reference,
                raw_payload,
                correlation_id
            )
            values (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                $11, $12, $13::jsonb, $14
            )
            on conflict (
                asset_id,
                platform_id,
                observed_at,
                variant_key,
                source_type,
                source_reference
            ) do update set
                raw_payload = market_observations.raw_payload || excluded.raw_payload
            returning id
            """,
            asset_db_id,
            platform_db_id,
            observation.observed_at,
            observation.price,
            observation.currency,
            observation.volume,
            observation.liquidity_score,
            observation.spread,
            observation.float_value,
            variant_key,
            observation.source_type.value,
            observation.source_reference or "",
            _jsonb(observation.raw_payload),
            observation.correlation_id,
        )
        return UUID(str(row["id"]))


@dataclass(slots=True)
class OutboxRepository:
    connection: asyncpg.Connection

    async def add_event(self, event: DomainEventContract) -> UUID:
        row = await self.connection.fetchrow(
            """
            insert into outbox_events (
                event_id,
                event_type,
                aggregate_id,
                payload,
                status,
                created_at,
                processed_at,
                error_message,
                correlation_id
            )
            values ($1, $2, $3, $4::jsonb, $5, $6, $7, $8, $9)
            returning event_id
            """,
            event.event_id,
            event.event_type.value,
            event.aggregate_id,
            _jsonb(event.payload),
            event.status.value,
            event.created_at,
            event.processed_at,
            event.error_message,
            event.correlation_id,
        )
        return UUID(str(row["event_id"]))

    async def fetch_pending(self, *, limit: int = 100) -> tuple[DomainEventContract, ...]:
        rows = await self.connection.fetch(
            """
            select *
            from outbox_events
            where status = 'pending'
            order by created_at
            limit $1
            """,
            limit,
        )
        return tuple(_event_from_record(row) for row in rows)

    async def mark_processing(self, event_id: UUID) -> None:
        await self._mark_status(event_id, EventStatus.PROCESSING)

    async def mark_processed(self, event_id: UUID) -> None:
        await self.connection.execute(
            """
            update outbox_events
            set status = $2, processed_at = $3, error_message = null
            where event_id = $1
            """,
            event_id,
            EventStatus.PROCESSED.value,
            datetime.now(tz=UTC),
        )

    async def mark_failed(self, event_id: UUID, error_message: str) -> None:
        await self.connection.execute(
            """
            update outbox_events
            set status = $2, error_message = $3
            where event_id = $1
            """,
            event_id,
            EventStatus.FAILED.value,
            error_message,
        )

    async def _mark_status(self, event_id: UUID, status: EventStatus) -> None:
        await self.connection.execute(
            "update outbox_events set status = $2 where event_id = $1",
            event_id,
            status.value,
        )


@dataclass(slots=True)
class MarketObservationIngestionRepository:
    connection: asyncpg.Connection

    async def record_observation(
        self,
        observation: MarketObservationContract,
        *,
        asset_name: str | None = None,
        category: str | None = None,
        quality: str | None = None,
        variant_key: str = "default",
    ) -> UUID:
        assets = AssetRepository(self.connection)
        platforms = PlatformRepository(self.connection)
        observations = MarketObservationRepository(self.connection)
        outbox = OutboxRepository(self.connection)

        async with self.connection.transaction():
            asset_db_id = await assets.upsert_asset(
                canonical_id=observation.asset_id,
                name=asset_name or observation.asset_id,
                category=category,
                quality=quality,
            )
            platform_db_id = await platforms.get_platform_id(observation.platform_id)
            observation_id = await observations.insert_observation(
                observation,
                asset_db_id=asset_db_id,
                platform_db_id=platform_db_id,
                variant_key=variant_key,
            )
            event = DomainEventContract(
                event_type=DomainEventType.MARKET_OBSERVATION_CAPTURED,
                aggregate_id=str(observation_id),
                payload=observation.model_dump(mode="json"),
                correlation_id=observation.correlation_id,
            )
            await outbox.add_event(event)
            return observation_id


@dataclass(slots=True)
class OutboxDispatcher:
    repository: OutboxRepository
    handlers: dict[DomainEventType, EventHandler]

    async def dispatch_pending(self, *, limit: int = 100) -> int:
        processed = 0
        for event in await self.repository.fetch_pending(limit=limit):
            handler = self.handlers.get(event.event_type)
            if handler is None:
                continue
            await self.repository.mark_processing(event.event_id)
            try:
                await handler(event)
            except Exception as exc:
                await self.repository.mark_failed(event.event_id, str(exc))
                continue
            await self.repository.mark_processed(event.event_id)
            processed += 1
        return processed


def _event_from_record(row: asyncpg.Record) -> DomainEventContract:
    payload = row["payload"]
    if isinstance(payload, str):
        payload = json.loads(payload)
    return DomainEventContract(
        event_id=row["event_id"],
        event_type=row["event_type"],
        aggregate_id=row["aggregate_id"],
        payload=dict(payload),
        status=row["status"],
        created_at=row["created_at"],
        processed_at=row["processed_at"],
        error_message=row["error_message"],
        correlation_id=row["correlation_id"],
    )


def _jsonb(value: dict[str, Any] | Sequence[Any]) -> str:
    return json.dumps(value)

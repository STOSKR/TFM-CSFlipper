"""Contracts for persisted domain events and the outbox."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import Field, field_validator

from packages.domain.enums import DomainEventType, EventStatus

from .base import ContractModel


class DomainEventContract(ContractModel):
    """Versioned outbox event contract."""

    event_id: UUID = Field(default_factory=uuid4)
    event_type: DomainEventType
    aggregate_id: str = Field(min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)
    status: EventStatus = EventStatus.PENDING
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    processed_at: datetime | None = None
    error_message: str | None = None
    correlation_id: str = Field(min_length=1)

    @field_validator("created_at", "processed_at")
    @classmethod
    def timestamps_must_be_timezone_aware(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return value
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("event timestamps must include timezone information")
        return value

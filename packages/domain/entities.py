"""Pure domain entities independent from frameworks and persistence."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from types import MappingProxyType
from typing import Any

from .enums import DecisionType, DomainEventType, EventStatus, SourceType, VoteChoice


@dataclass(frozen=True, slots=True)
class AssetIdentity:
    canonical_id: str
    name: str
    category: str | None = None
    quality: str | None = None
    rarity: str | None = None
    stattrak: bool = False
    souvenir: bool = False
    external_identifiers: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PlatformIdentity:
    code: str
    name: str
    fee_percentage: Decimal | None = None


@dataclass(frozen=True, slots=True)
class MarketObservation:
    asset_id: str
    platform_id: str
    observed_at: datetime
    price: Decimal
    currency: str
    source_type: SourceType
    volume: int | None = None
    liquidity_score: Decimal | None = None
    spread: Decimal | None = None
    float_value: Decimal | None = None
    source_reference: str | None = None
    raw_payload: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_timezone(self.observed_at, "observed_at")
        _require_positive_decimal(self.price, "price")
        if len(self.currency.strip()) != 3:
            raise ValueError("currency must be a 3-letter code")
        object.__setattr__(self, "currency", self.currency.upper())
        object.__setattr__(self, "raw_payload", MappingProxyType(dict(self.raw_payload)))


@dataclass(frozen=True, slots=True)
class Prediction:
    prediction_id: str
    asset_id: str
    platform_id: str
    probability_up: Decimal
    expected_return: Decimal
    confidence: Decimal
    prediction_horizon: str
    model_name: str
    model_version: str
    created_at: datetime
    correlation_id: str
    features_snapshot: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_timezone(self.created_at, "created_at")
        _require_probability(self.probability_up, "probability_up")
        _require_probability(self.confidence, "confidence")
        object.__setattr__(
            self, "features_snapshot", MappingProxyType(dict(self.features_snapshot))
        )


@dataclass(frozen=True, slots=True)
class Vote:
    prediction_id: str
    risk_profile_id: str
    agent_jid: str
    vote: VoteChoice
    confidence: Decimal
    reason: str
    created_at: datetime
    correlation_id: str

    def __post_init__(self) -> None:
        _require_timezone(self.created_at, "created_at")
        _require_probability(self.confidence, "confidence")


@dataclass(frozen=True, slots=True)
class InvestmentDecision:
    decision_id: str
    prediction_id: str
    decision: DecisionType
    consensus_score: Decimal
    reason: str
    created_at: datetime
    correlation_id: str

    def __post_init__(self) -> None:
        _require_timezone(self.created_at, "created_at")
        _require_probability(self.consensus_score, "consensus_score")


@dataclass(frozen=True, slots=True)
class OutboxEvent:
    event_id: str
    event_type: DomainEventType
    aggregate_id: str
    payload: Mapping[str, Any]
    correlation_id: str
    created_at: datetime
    status: EventStatus = EventStatus.PENDING
    processed_at: datetime | None = None
    error_message: str | None = None

    def __post_init__(self) -> None:
        _require_timezone(self.created_at, "created_at")
        if self.processed_at is not None:
            _require_timezone(self.processed_at, "processed_at")
        object.__setattr__(self, "payload", MappingProxyType(dict(self.payload)))


def _require_timezone(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must include timezone information")


def _require_positive_decimal(value: Decimal, field_name: str) -> None:
    if value <= Decimal("0"):
        raise ValueError(f"{field_name} must be greater than zero")


def _require_probability(value: Decimal, field_name: str) -> None:
    if value < Decimal("0") or value > Decimal("1"):
        raise ValueError(f"{field_name} must be between 0 and 1")

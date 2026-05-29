"""Shared domain enumerations."""

from __future__ import annotations

from enum import StrEnum


class SourceType(StrEnum):
    """Origin of a normalized market observation."""

    API = "api"
    SCRAPING = "scraping"
    OCR = "ocr"
    CSV = "csv"
    LEGACY_SUPABASE = "legacy_supabase"


class VoteChoice(StrEnum):
    """Possible vote emitted by a risk profile."""

    BUY = "buy"
    REJECT = "reject"
    OBSERVE = "observe"
    ABSTAIN = "abstain"


class DecisionType(StrEnum):
    """Final simulated decision types."""

    SIMULATED_BUY = "COMPRA_SIMULADA"
    REJECT = "RECHAZO"
    KEEP_WATCHING = "MANTENER_OBSERVACION"
    INSUFFICIENT_DATA = "ERROR_DATOS_INSUFICIENTES"


class EventStatus(StrEnum):
    """Outbox event processing status."""

    PENDING = "pending"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"


class DomainEventType(StrEnum):
    """Domain events expected by the operational flow."""

    MARKET_OBSERVATION_CAPTURED = "MarketObservationCaptured"
    PREDICTION_REQUESTED = "PredictionRequested"
    PREDICTION_COMPLETED = "PredictionCompleted"
    VOTE_REQUESTED = "VoteRequested"
    VOTE_SUBMITTED = "VoteSubmitted"
    INVESTMENT_DECISION_MADE = "InvestmentDecisionMade"

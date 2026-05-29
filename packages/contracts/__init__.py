"""Pydantic contracts shared by apps, agents and persistence."""

from .events import DomainEventContract
from .legacy import LegacyScrapedItemContract
from .messages import (
    InvestmentDecisionMadeMessage,
    PredictionCompletedMessage,
    VoteRequestedMessage,
    VoteSubmittedMessage,
)
from .observations import MarketObservationContract

__all__ = [
    "DomainEventContract",
    "InvestmentDecisionMadeMessage",
    "LegacyScrapedItemContract",
    "MarketObservationContract",
    "PredictionCompletedMessage",
    "VoteRequestedMessage",
    "VoteSubmittedMessage",
]

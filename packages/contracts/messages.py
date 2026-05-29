"""Agent message contracts."""

from __future__ import annotations

from decimal import Decimal

from pydantic import Field

from packages.domain.enums import DecisionType, VoteChoice

from .base import ContractModel


class PredictionCompletedMessage(ContractModel):
    correlation_id: str = Field(min_length=1)
    prediction_id: str = Field(min_length=1)
    asset_id: str = Field(min_length=1)
    platform_id: str = Field(min_length=1)
    probability_up: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    expected_return: Decimal
    confidence: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    prediction_horizon: str = Field(min_length=1)


class VoteRequestedMessage(ContractModel):
    correlation_id: str = Field(min_length=1)
    prediction_id: str = Field(min_length=1)
    risk_profile_id: str = Field(min_length=1)
    deadline_seconds: int = Field(gt=0)


class VoteSubmittedMessage(ContractModel):
    correlation_id: str = Field(min_length=1)
    prediction_id: str = Field(min_length=1)
    risk_profile_id: str = Field(min_length=1)
    agent_jid: str = Field(min_length=1)
    vote: VoteChoice
    confidence: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    reason: str = Field(min_length=1)


class InvestmentDecisionMadeMessage(ContractModel):
    correlation_id: str = Field(min_length=1)
    decision_id: str = Field(min_length=1)
    prediction_id: str = Field(min_length=1)
    decision: DecisionType
    consensus_score: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    reason: str = Field(min_length=1)

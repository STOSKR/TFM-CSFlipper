"""Contracts for normalized market observations."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import Field, field_validator

from packages.domain.enums import SourceType

from .base import ContractModel


class MarketObservationContract(ContractModel):
    """Normalized observation emitted by CSV, OCR, scraping or API acquisition."""

    correlation_id: str = Field(min_length=1)
    asset_id: str = Field(min_length=1)
    platform_id: str = Field(min_length=1)
    observed_at: datetime
    price: Decimal = Field(gt=Decimal("0"))
    currency: str = Field(min_length=3, max_length=3)
    source_type: SourceType
    volume: int | None = Field(default=None, ge=0)
    liquidity_score: Decimal | None = Field(default=None, ge=Decimal("0"), le=Decimal("1"))
    spread: Decimal | None = Field(default=None, ge=Decimal("0"))
    float_value: Decimal | None = Field(default=None, ge=Decimal("0"), le=Decimal("1"))
    source_reference: str | None = None
    raw_payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("observed_at")
    @classmethod
    def observed_at_must_be_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("observed_at must include timezone information")
        return value

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()

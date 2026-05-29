"""Contracts for legacy sources that will be adapted into the canonical model."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from pydantic import Field, field_validator

from .base import ContractModel


class LegacyScrapedItemContract(ContractModel):
    """Row shape used by the existing cs-tracker `scraped_items` Supabase table."""

    id: int | None = Field(default=None, ge=1)
    item_name: str = Field(min_length=1)
    quality: str | None = None
    stattrak: bool = False
    profitability: Decimal | None = None
    profit_eur: Decimal | None = None
    buff_url: str | None = None
    buff_price_eur: Decimal = Field(gt=Decimal("0"))
    steam_url: str | None = None
    steam_price_eur: Decimal = Field(gt=Decimal("0"))
    scraped_at: datetime
    source: str = Field(default="steamdt_hanging", min_length=1)
    created_at: datetime | None = None

    @field_validator("scraped_at", "created_at", mode="before")
    @classmethod
    def parse_legacy_timestamp(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        normalized = value.strip()
        if normalized.endswith("Z"):
            normalized = f"{normalized[:-1]}+00:00"
        return datetime.fromisoformat(normalized)

    @field_validator("scraped_at", "created_at")
    @classmethod
    def timestamps_must_be_timezone_aware(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return value
        if value.tzinfo is None or value.utcoffset() is None:
            return value.replace(tzinfo=UTC)
        return value

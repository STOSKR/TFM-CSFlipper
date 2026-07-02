"""Persistence helpers for market opportunity signals."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID


@dataclass(frozen=True, slots=True)
class MarketOpportunitySignal:
    item_id: UUID
    model_name: str
    model_version: str
    route_label: str
    buy_platform: str
    buy_price_type: str
    sell_platform: str
    sell_price_type: str
    status: str
    reason: str
    data_quality_status: str
    observed_at: datetime | None = None
    correlation_id: str | None = None
    prediction_horizon: str = "8d"
    buy_price_eur: Decimal | None = None
    exit_value_eur: Decimal | None = None
    expected_profit_eur: Decimal | None = None
    expected_return: Decimal | None = None
    probability_profitable: Decimal | None = None
    decision_threshold: Decimal | None = None
    is_signal: bool = False
    missing_fields: tuple[str, ...] = ()
    feature_snapshot: Mapping[str, Any] = field(default_factory=dict)
    model_output: Mapping[str, Any] = field(default_factory=dict)


class MarketOpportunitySignalRepository:
    def __init__(self, connection: Any) -> None:
        self._connection = connection

    async def record_signals(self, signals: Sequence[MarketOpportunitySignal]) -> int:
        if not signals:
            return 0
        await self._connection.executemany(
            """
            insert into market_opportunity_signals (
                item_id,
                observed_at,
                correlation_id,
                model_name,
                model_version,
                prediction_horizon,
                route_label,
                buy_platform,
                buy_price_type,
                sell_platform,
                sell_price_type,
                buy_price_eur,
                exit_value_eur,
                expected_profit_eur,
                expected_return,
                probability_profitable,
                decision_threshold,
                is_signal,
                status,
                reason,
                data_quality_status,
                missing_fields,
                feature_snapshot,
                model_output
            )
            values (
                $1, $2, $3, $4, $5, $6, $7, $8,
                $9, $10, $11, $12, $13, $14, $15, $16,
                $17, $18, $19, $20, $21, $22, $23::jsonb, $24::jsonb
            )
            """,
            [_record_args(signal) for signal in signals],
        )
        return len(signals)


def _record_args(signal: MarketOpportunitySignal) -> tuple[Any, ...]:
    return (
        signal.item_id,
        signal.observed_at,
        signal.correlation_id,
        signal.model_name,
        signal.model_version,
        signal.prediction_horizon,
        signal.route_label,
        signal.buy_platform,
        signal.buy_price_type,
        signal.sell_platform,
        signal.sell_price_type,
        signal.buy_price_eur,
        signal.exit_value_eur,
        signal.expected_profit_eur,
        signal.expected_return,
        signal.probability_profitable,
        signal.decision_threshold,
        signal.is_signal,
        signal.status,
        signal.reason,
        signal.data_quality_status,
        list(signal.missing_fields),
        json.dumps(signal.feature_snapshot, default=str),
        json.dumps(signal.model_output, default=str),
    )

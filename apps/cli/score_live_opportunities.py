"""Score current market items into market_opportunity_signals."""

from __future__ import annotations

import argparse
import asyncio
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

from packages.persistence.connection import create_pool
from packages.persistence.opportunity_signals import (
    MarketOpportunitySignal,
    MarketOpportunitySignalRepository,
)
from packages.runtime_config import load_runtime_config
from packages.simulation import BUFF163, STEAM
from packages.simulation.economics import (
    MarketEconomicsConfig,
    default_excel_economics_config,
    net_sale_value_eur,
    return_ratio,
)

MODEL_NAME = "current_spread_baseline"
MODEL_VERSION = "v1"
DECISION_THRESHOLD = Decimal("0.60")


@dataclass(frozen=True, slots=True)
class ScoreSummary:
    loaded: int
    scored: int
    inserted: int
    review: int
    observe: int
    blocked: int


async def run(args: argparse.Namespace) -> ScoreSummary:
    runtime_config = load_runtime_config(args.config)
    economics = default_excel_economics_config(
        cny_per_eur=Decimal(str(args.cny_per_eur)),
        trade_hold_days=args.horizon_days,
    )
    economics = MarketEconomicsConfig(
        cny_per_eur=economics.cny_per_eur,
        trade_hold_days=economics.trade_hold_days,
        sale_fee_factors=economics.sale_fee_factors,
        steam_cashout_loss=runtime_config.fees.withdrawal_rate,
        steam_cashout_loss_scenarios=economics.steam_cashout_loss_scenarios,
    )
    rows = await _load_market_items(limit=args.limit)
    scored_at = datetime.now(tz=UTC)
    correlation_id = f"opportunity-score:{scored_at.strftime('%Y%m%d_%H%M%S')}"
    signals = tuple(
        _score_row(
            row,
            economics=economics,
            correlation_id=correlation_id,
            min_profit_eur=Decimal(str(args.min_profit_eur)),
            min_return=Decimal(str(args.min_return)),
        )
        for row in rows
    )
    inserted = 0
    if args.persist and not args.dry_run:
        pool = await create_pool(max_size=2)
        try:
            async with pool.acquire() as connection:
                inserted = await MarketOpportunitySignalRepository(connection).record_signals(
                    signals
                )
        finally:
            await pool.close()
    _print_lines(signals, verbose=args.verbose)
    summary = ScoreSummary(
        loaded=len(rows),
        scored=len(signals),
        inserted=inserted,
        review=sum(1 for signal in signals if signal.status == "review"),
        observe=sum(1 for signal in signals if signal.status == "observe"),
        blocked=sum(1 for signal in signals if signal.status == "blocked"),
    )
    print(
        "opportunity_summary "
        f"loaded={summary.loaded} scored={summary.scored} inserted={summary.inserted} "
        f"review={summary.review} observe={summary.observe} blocked={summary.blocked}"
    )
    return summary


async def _load_market_items(*, limit: int | None) -> tuple[dict[str, Any], ...]:
    pool = await create_pool(max_size=2)
    try:
        async with pool.acquire() as connection:
            rows = await connection.fetch(
                """
                select
                    id,
                    representation_name,
                    name,
                    quality,
                    stattrak,
                    scraped_at,
                    last_checked_at,
                    steam_price_eur,
                    buff_price_eur,
                    steam_price,
                    steam_currency,
                    buff_price,
                    buff_currency
                from market_items
                order by coalesce(last_checked_at, scraped_at, updated_at, created_at) desc
                limit $1
                """,
                limit,
            )
    finally:
        await pool.close()
    return tuple(dict(row) for row in rows)


def _score_row(
    row: Mapping[str, Any],
    *,
    economics: MarketEconomicsConfig,
    correlation_id: str,
    min_profit_eur: Decimal,
    min_return: Decimal,
) -> MarketOpportunitySignal:
    missing = tuple(
        field
        for field in ("steam_price_eur", "buff_price_eur")
        if _decimal_or_none(row.get(field)) is None
    )
    observed_at = _observed_at(row)
    feature_snapshot = _feature_snapshot(row)
    if missing:
        return MarketOpportunitySignal(
            item_id=UUID(str(row["id"])),
            observed_at=observed_at,
            correlation_id=correlation_id,
            model_name=MODEL_NAME,
            model_version=MODEL_VERSION,
            route_label="BUFF listing -> STEAM listing",
            buy_platform=BUFF163,
            buy_price_type="listing",
            sell_platform=STEAM,
            sell_price_type="listing",
            status="blocked",
            reason="missing required live prices: " + ", ".join(missing),
            data_quality_status="missing_data",
            missing_fields=missing,
            feature_snapshot=feature_snapshot,
            model_output={"scorer": MODEL_NAME, "usable": False},
        )

    steam_price_eur = _decimal_or_none(row.get("steam_price_eur"))
    buff_price_eur = _decimal_or_none(row.get("buff_price_eur"))
    assert steam_price_eur is not None
    assert buff_price_eur is not None
    exit_value_eur = net_sale_value_eur(
        steam_price_eur,
        sale_platform=STEAM,
        sale_currency="EUR",
        config=economics,
    )
    expected_profit = exit_value_eur - buff_price_eur
    expected_return = return_ratio(expected_profit, buff_price_eur)
    probability = _baseline_probability(expected_return)
    is_signal = (
        probability >= DECISION_THRESHOLD
        and expected_profit >= min_profit_eur
        and expected_return >= min_return
    )
    status = "review" if is_signal else "observe"
    reason = (
        "positive net spread above threshold"
        if is_signal
        else "net spread or probability below threshold"
    )
    return MarketOpportunitySignal(
        item_id=UUID(str(row["id"])),
        observed_at=observed_at,
        correlation_id=correlation_id,
        model_name=MODEL_NAME,
        model_version=MODEL_VERSION,
        route_label="BUFF listing -> STEAM listing",
        buy_platform=BUFF163,
        buy_price_type="listing",
        sell_platform=STEAM,
        sell_price_type="listing",
        buy_price_eur=buff_price_eur,
        exit_value_eur=exit_value_eur,
        expected_profit_eur=expected_profit,
        expected_return=expected_return,
        probability_profitable=probability,
        decision_threshold=DECISION_THRESHOLD,
        is_signal=is_signal,
        status=status,
        reason=reason,
        data_quality_status="ok",
        feature_snapshot={
            **feature_snapshot,
            "steam_net_sale_eur": str(exit_value_eur),
            "min_profit_eur": str(min_profit_eur),
            "min_return": str(min_return),
        },
        model_output={
            "scorer": MODEL_NAME,
            "probability_source": "heuristic_current_return",
            "expected_profit_eur": str(expected_profit),
            "expected_return": str(expected_return),
        },
    )


def _baseline_probability(expected_return: Decimal) -> Decimal:
    raw = Decimal("0.50") + expected_return * Decimal("5")
    return min(Decimal("0.99"), max(Decimal("0.01"), raw)).quantize(Decimal("0.00001"))


def _feature_snapshot(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "representation_name": row.get("representation_name"),
        "name": row.get("name"),
        "quality": row.get("quality"),
        "stattrak": row.get("stattrak"),
        "scraped_at": _text_or_none(row.get("scraped_at")),
        "last_checked_at": _text_or_none(row.get("last_checked_at")),
        "steam_price": _text_or_none(row.get("steam_price")),
        "steam_currency": row.get("steam_currency"),
        "steam_price_eur": _text_or_none(row.get("steam_price_eur")),
        "buff_price": _text_or_none(row.get("buff_price")),
        "buff_currency": row.get("buff_currency"),
        "buff_price_eur": _text_or_none(row.get("buff_price_eur")),
    }


def _observed_at(row: Mapping[str, Any]) -> datetime | None:
    for key in ("last_checked_at", "scraped_at"):
        value = row.get(key)
        if isinstance(value, datetime):
            return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)
    return None


def _decimal_or_none(value: Any) -> Decimal | None:
    if value is None:
        return None
    text = str(value).strip()
    return Decimal(text) if text else None


def _text_or_none(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _print_lines(signals: Sequence[MarketOpportunitySignal], *, verbose: bool) -> None:
    if not verbose:
        return
    for signal in signals:
        print(
            "opportunity "
            f"item_id={signal.item_id} status={signal.status} "
            f"profit={signal.expected_profit_eur} return={signal.expected_return} "
            f"probability={signal.probability_profitable} reason={signal.reason}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Score live market opportunity signals.")
    parser.add_argument("--config", type=Path, default=Path("csflipper_config.toml"))
    parser.add_argument("--limit", type=int, default=250)
    parser.add_argument("--horizon-days", type=int, default=8)
    parser.add_argument("--cny-per-eur", type=str, default="8")
    parser.add_argument("--min-profit-eur", type=str, default="0")
    parser.add_argument("--min-return", type=str, default="0")
    parser.add_argument("--persist", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()

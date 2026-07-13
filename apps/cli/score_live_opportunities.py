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
from packages.prediction.steam_buff_flip import score_buff_to_steam_flip
from packages.runtime_config import load_runtime_config
from packages.simulation.economics import (
    MarketEconomicsConfig,
    default_excel_economics_config,
)

MODEL_NAME = "steam_exit_flip_recommendation"
MODEL_VERSION = "baseline_v1"


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
    observed_at = _observed_at(row)
    feature_snapshot = _feature_snapshot(row)
    steam_price_eur = _decimal_or_none(row.get("steam_price_eur"))
    buff_price_eur = _decimal_or_none(row.get("buff_price_eur"))
    expected_steam_return_8d = _decimal_or_none(
        row.get("expected_steam_return_8d") or row.get("steam_expected_return_8d")
    )
    probability_safe_exit = _decimal_or_none(
        row.get("probability_safe_exit")
        or row.get("steam_safe_exit_probability")
        or row.get("direction_up_probability")
    )
    flip_score = score_buff_to_steam_flip(
        steam_price_eur=steam_price_eur,
        buff_entry_price_eur=buff_price_eur,
        economics=economics,
        min_profit_eur=min_profit_eur,
        min_return=min_return,
        probability_safe_exit=probability_safe_exit,
        expected_steam_return_8d=expected_steam_return_8d,
    )
    if flip_score.data_quality_status != "ok":
        return MarketOpportunitySignal(
            item_id=UUID(str(row["id"])),
            observed_at=observed_at,
            correlation_id=correlation_id,
            model_name=MODEL_NAME,
            model_version=MODEL_VERSION,
            route_label=flip_score.route_label,
            buy_platform=flip_score.buy_platform,
            buy_price_type=flip_score.buy_price_type,
            sell_platform=flip_score.sell_platform,
            sell_price_type=flip_score.sell_price_type,
            status=flip_score.status,
            reason=flip_score.reason,
            data_quality_status=flip_score.data_quality_status,
            missing_fields=flip_score.missing_fields,
            feature_snapshot=feature_snapshot,
            model_output={
                "scorer": MODEL_NAME,
                "usable": False,
                "probability_safe_exit": _text_or_none(flip_score.probability_safe_exit),
                "expected_steam_return_8d": _text_or_none(
                    flip_score.expected_steam_return_8d
                ),
                "risk_level": flip_score.risk_level,
                "probability_source": flip_score.probability_source,
                "note": "BUFF is a live entry quote, not a training target",
            },
        )

    return MarketOpportunitySignal(
        item_id=UUID(str(row["id"])),
        observed_at=observed_at,
        correlation_id=correlation_id,
        model_name=MODEL_NAME,
        model_version=MODEL_VERSION,
        route_label=flip_score.route_label,
        buy_platform=flip_score.buy_platform,
        buy_price_type=flip_score.buy_price_type,
        sell_platform=flip_score.sell_platform,
        sell_price_type=flip_score.sell_price_type,
        buy_price_eur=flip_score.buy_price_eur,
        exit_value_eur=flip_score.exit_value_eur,
        expected_profit_eur=flip_score.expected_profit_eur,
        expected_return=flip_score.expected_return,
        probability_profitable=flip_score.probability_safe_exit,
        decision_threshold=flip_score.decision_threshold,
        is_signal=flip_score.is_signal,
        status=flip_score.status,
        reason=flip_score.reason,
        data_quality_status="ok",
        feature_snapshot={
            **feature_snapshot,
            "expected_steam_return_8d": _text_or_none(flip_score.expected_steam_return_8d),
            "steam_exit_value_eur": _text_or_none(flip_score.exit_value_eur),
            "min_profit_eur": str(min_profit_eur),
            "min_return": str(min_return),
        },
        model_output={
            "scorer": MODEL_NAME,
            "probability_safe_exit": _text_or_none(flip_score.probability_safe_exit),
            "expected_steam_return_8d": _text_or_none(flip_score.expected_steam_return_8d),
            "expected_profit_eur": _text_or_none(flip_score.expected_profit_eur),
            "expected_return": _text_or_none(flip_score.expected_return),
            "risk_level": flip_score.risk_level,
            "recommendation": flip_score.status,
            "probability_source": flip_score.probability_source,
            "buff_role": "live_entry_price_only",
            "steam_role": "trained_exit_risk",
        },
    )


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

"""Steam-trained exit risk scoring for BUFF-to-Steam flip recommendations."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from packages.simulation import BUFF, STEAM
from packages.simulation.economics import (
    MarketEconomicsConfig,
    net_sale_value_eur,
    return_ratio,
)

DEFAULT_SAFE_EXIT_THRESHOLD = Decimal("0.60")


@dataclass(frozen=True, slots=True)
class SteamBuffFlipScore:
    """Decision-ready score for a candidate bought on BUFF and exited on Steam."""

    route_label: str
    buy_platform: str
    buy_price_type: str
    sell_platform: str
    sell_price_type: str
    status: str
    reason: str
    data_quality_status: str
    missing_fields: tuple[str, ...]
    buy_price_eur: Decimal | None
    exit_value_eur: Decimal | None
    expected_profit_eur: Decimal | None
    expected_return: Decimal | None
    probability_safe_exit: Decimal | None
    expected_steam_return_8d: Decimal | None
    decision_threshold: Decimal
    is_signal: bool
    risk_level: str
    probability_source: str


def score_buff_to_steam_flip(
    *,
    steam_price_eur: Decimal | None,
    buff_entry_price_eur: Decimal | None,
    economics: MarketEconomicsConfig,
    min_profit_eur: Decimal = Decimal("0"),
    min_return: Decimal = Decimal("0"),
    probability_safe_exit: Decimal | None = None,
    expected_steam_return_8d: Decimal | None = None,
    decision_threshold: Decimal = DEFAULT_SAFE_EXIT_THRESHOLD,
) -> SteamBuffFlipScore:
    """Score a flip using BUFF only as live entry price and Steam as exit model.

    The function does not infer or predict BUFF prices. BUFF is a point-in-time
    entry quote. Steam carries the temporal risk through a safe-exit probability
    and optional expected return.
    """

    if steam_price_eur is None:
        return _missing_score(
            status="blocked",
            reason="missing live Steam exit price",
            data_quality_status="missing_exit_price",
            missing_fields=("steam_price_eur",),
            probability_safe_exit=probability_safe_exit,
            expected_steam_return_8d=expected_steam_return_8d,
            decision_threshold=decision_threshold,
        )
    if buff_entry_price_eur is None:
        return _missing_score(
            status="observe",
            reason=(
                "missing live BUFF entry price; "
                "Steam exit risk can be scored but flip cannot be priced"
            ),
            data_quality_status="missing_entry_price",
            missing_fields=("buff_price_eur",),
            probability_safe_exit=probability_safe_exit,
            expected_steam_return_8d=expected_steam_return_8d,
            decision_threshold=decision_threshold,
        )

    expected_steam_return = expected_steam_return_8d or Decimal("0")
    expected_steam_gross_eur = steam_price_eur * (Decimal("1") + expected_steam_return)
    exit_value_eur = net_sale_value_eur(
        expected_steam_gross_eur,
        sale_platform=STEAM,
        sale_currency="EUR",
        config=economics,
    )
    expected_profit_eur = exit_value_eur - buff_entry_price_eur
    expected_return = return_ratio(expected_profit_eur, buff_entry_price_eur)
    probability_source = "steam_exit_model"
    if probability_safe_exit is None:
        probability_safe_exit = baseline_safe_exit_probability(expected_return)
        probability_source = "heuristic_current_margin"

    is_signal = (
        probability_safe_exit >= decision_threshold
        and expected_profit_eur >= min_profit_eur
        and expected_return >= min_return
    )
    risk_level = risk_level_from_exit(
        probability_safe_exit=probability_safe_exit,
        expected_return=expected_return,
    )
    return SteamBuffFlipScore(
        route_label="BUFF listing -> Steam listing",
        buy_platform=BUFF,
        buy_price_type="listing",
        sell_platform=STEAM,
        sell_price_type="listing",
        status="review" if is_signal else "observe",
        reason=(
            "positive BUFF entry margin and Steam safe-exit probability above threshold"
            if is_signal
            else "entry margin, expected return or Steam safe-exit probability below threshold"
        ),
        data_quality_status="ok",
        missing_fields=(),
        buy_price_eur=buff_entry_price_eur,
        exit_value_eur=exit_value_eur,
        expected_profit_eur=expected_profit_eur,
        expected_return=expected_return,
        probability_safe_exit=probability_safe_exit,
        expected_steam_return_8d=expected_steam_return,
        decision_threshold=decision_threshold,
        is_signal=is_signal,
        risk_level=risk_level,
        probability_source=probability_source,
    )


def baseline_safe_exit_probability(expected_return: Decimal) -> Decimal:
    """Conservative deterministic fallback until a Steam-only model is wired live."""

    raw = Decimal("0.50") + expected_return * Decimal("5")
    return min(Decimal("0.99"), max(Decimal("0.01"), raw)).quantize(Decimal("0.00001"))


def risk_level_from_exit(
    *,
    probability_safe_exit: Decimal,
    expected_return: Decimal | None,
) -> str:
    expected = expected_return or Decimal("0")
    if probability_safe_exit >= Decimal("0.75") and expected >= Decimal("0.05"):
        return "low"
    if probability_safe_exit >= Decimal("0.55") and expected >= Decimal("0"):
        return "medium"
    return "high"


def _missing_score(
    *,
    status: str,
    reason: str,
    data_quality_status: str,
    missing_fields: tuple[str, ...],
    probability_safe_exit: Decimal | None,
    expected_steam_return_8d: Decimal | None,
    decision_threshold: Decimal,
) -> SteamBuffFlipScore:
    return SteamBuffFlipScore(
        route_label="BUFF listing -> Steam listing",
        buy_platform=BUFF,
        buy_price_type="listing",
        sell_platform=STEAM,
        sell_price_type="listing",
        status=status,
        reason=reason,
        data_quality_status=data_quality_status,
        missing_fields=missing_fields,
        buy_price_eur=None,
        exit_value_eur=None,
        expected_profit_eur=None,
        expected_return=None,
        probability_safe_exit=probability_safe_exit,
        expected_steam_return_8d=expected_steam_return_8d,
        decision_threshold=decision_threshold,
        is_signal=False,
        risk_level="unknown",
        probability_source=(
            "steam_exit_model" if probability_safe_exit is not None else "unavailable"
        ),
    )

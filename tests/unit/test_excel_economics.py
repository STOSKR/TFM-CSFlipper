from datetime import date
from decimal import Decimal

import pytest

from packages.simulation import (
    BUFF163,
    CSFLOAT,
    SKINPORT,
    STEAM,
    PositionStatus,
    calculate_trade_result,
    convert_currency,
    default_excel_economics_config,
    effective_cash_value,
    return_ratio,
    unlock_date,
)
from packages.simulation.economics import position_status, steam_balance_cost_factor


def test_convert_currency_matches_excel_rate() -> None:
    config = default_excel_economics_config(cny_per_eur=Decimal("8"))

    assert convert_currency(
        Decimal("188"),
        source_currency="CNY",
        target_currency="EUR",
        cny_per_eur=config.cny_per_eur,
    ) == Decimal("23.5")
    assert convert_currency(
        Decimal("41.1"),
        source_currency="EUR",
        target_currency="CNY",
        cny_per_eur=config.cny_per_eur,
    ) == Decimal("328.8")


def test_buff_purchase_to_steam_sale_result_matches_historial_formula() -> None:
    config = default_excel_economics_config(cny_per_eur=Decimal("8"))

    result = calculate_trade_result(
        buy_price=Decimal("188"),
        buy_currency="CNY",
        sell_price=Decimal("69.99"),
        sell_currency="EUR",
        sell_platform=STEAM,
        config=config,
    )

    assert result.buy_price_eur == Decimal("23.5")
    assert result.sell_price_eur == Decimal("69.99")
    assert result.realized_profit_eur == Decimal("46.49")
    assert result.return_ratio == Decimal("46.49") / Decimal("23.5")


def test_steam_purchase_to_buff_sale_applies_buff_fee() -> None:
    config = default_excel_economics_config(cny_per_eur=Decimal("8"))

    result = calculate_trade_result(
        buy_price=Decimal("41.1"),
        buy_currency="EUR",
        sell_price=Decimal("347.5"),
        sell_currency="CNY",
        sell_platform=BUFF163,
        config=config,
    )

    assert result.buy_price_eur == Decimal("41.1")
    assert result.sell_price_eur == Decimal("347.5") / Decimal("8") * Decimal("0.975")
    assert result.realized_profit_eur == result.sell_price_eur - Decimal("41.1")


def test_excel_unlock_date_uses_configured_plus_eight_days() -> None:
    config = default_excel_economics_config(trade_hold_days=8)

    assert unlock_date(date(2025, 11, 1), config=config) == date(2025, 11, 9)


def test_position_status_distinguishes_locked_open_and_closed() -> None:
    config = default_excel_economics_config(trade_hold_days=8)
    purchased_at = date(2025, 11, 1)

    assert (
        position_status(
            purchased_at=purchased_at,
            sold_at=None,
            as_of=date(2025, 11, 8),
            config=config,
        )
        == PositionStatus.LOCKED
    )
    assert (
        position_status(
            purchased_at=purchased_at,
            sold_at=None,
            as_of=date(2025, 11, 9),
            config=config,
        )
        == PositionStatus.OPEN
    )
    assert (
        position_status(
            purchased_at=purchased_at,
            sold_at=date(2025, 11, 10),
            as_of=date(2025, 11, 11),
            config=config,
        )
        == PositionStatus.CLOSED
    )


def test_effective_cash_and_fee_factors_match_calculators() -> None:
    config = default_excel_economics_config()

    assert effective_cash_value(Decimal("100"), platform=STEAM, config=config) == Decimal("80.0")
    assert effective_cash_value(Decimal("100"), platform=BUFF163, config=config) == Decimal("100")
    assert steam_balance_cost_factor(config) == Decimal("0.696")
    assert steam_balance_cost_factor(config, optimistic=True) == Decimal("0.783")
    assert config.sale_fee_factors[BUFF163] == Decimal("0.975")
    assert config.sale_fee_factors[CSFLOAT] == Decimal("0.98")
    assert config.sale_fee_factors[SKINPORT] == Decimal("0.93")


def test_return_ratio_guards_zero_invested_amount() -> None:
    assert return_ratio(Decimal("10"), Decimal("0")) == Decimal("0")


def test_unknown_sale_platform_fails_loudly() -> None:
    config = default_excel_economics_config()

    with pytest.raises(ValueError, match="missing sale fee factor"):
        calculate_trade_result(
            buy_price=Decimal("10"),
            buy_currency="EUR",
            sell_price=Decimal("12"),
            sell_currency="EUR",
            sell_platform="UNKNOWN",
            config=config,
        )


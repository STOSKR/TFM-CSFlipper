"""Economic formulas migrated from the operational Steam-Buff workbook."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType

STEAM = "STEAM"
BUFF163 = "BUFF"
CSFLOAT = "CSFLOAT"
SKINPORT = "SKINPORT"

EUR = "EUR"
CNY = "CNY"


class PositionStatus(StrEnum):
    LOCKED = "locked"
    OPEN = "open"
    CLOSED = "closed"


@dataclass(frozen=True, slots=True)
class MarketEconomicsConfig:
    """Versioned economic assumptions for fees, FX and trade hold."""

    cny_per_eur: Decimal
    trade_hold_days: int
    sale_fee_factors: dict[str, Decimal] = field(default_factory=dict)
    steam_cash_factor: Decimal = Decimal("0.8")
    steam_balance_discount: Decimal = Decimal("0.87")

    def __post_init__(self) -> None:
        if self.cny_per_eur <= 0:
            raise ValueError("cny_per_eur must be greater than zero")
        if self.trade_hold_days < 0:
            raise ValueError("trade_hold_days must be non-negative")
        for platform, factor in self.sale_fee_factors.items():
            if factor <= 0 or factor > 1:
                raise ValueError(f"sale fee factor for {platform} must be in (0, 1]")
        object.__setattr__(
            self,
            "sale_fee_factors",
            MappingProxyType({key.upper(): value for key, value in self.sale_fee_factors.items()}),
        )


@dataclass(frozen=True, slots=True)
class EconomicResult:
    buy_price_eur: Decimal
    sell_price_eur: Decimal
    realized_profit_eur: Decimal
    return_ratio: Decimal


def default_excel_economics_config(
    *,
    cny_per_eur: Decimal = Decimal("8"),
    trade_hold_days: int = 8,
) -> MarketEconomicsConfig:
    """Return the initial assumptions observed in the operational workbook.

    The workbook uses `Fecha C + 8`, so this default intentionally mirrors Excel.
    The TFM model can pass `trade_hold_days=7` once that convention is confirmed.
    """

    return MarketEconomicsConfig(
        cny_per_eur=cny_per_eur,
        trade_hold_days=trade_hold_days,
        sale_fee_factors={
            STEAM: Decimal("1"),
            BUFF163: Decimal("0.975"),
            CSFLOAT: Decimal("0.98"),
            SKINPORT: Decimal("0.93"),
        },
        steam_cash_factor=Decimal("0.8"),
        steam_balance_discount=Decimal("0.87"),
    )


def convert_currency(
    amount: Decimal,
    *,
    source_currency: str,
    target_currency: str,
    cny_per_eur: Decimal,
) -> Decimal:
    """Convert EUR/CNY amounts using a CNY per EUR rate."""

    _require_non_negative(amount, "amount")
    source = source_currency.upper()
    target = target_currency.upper()
    if source == target:
        return amount
    if source == CNY and target == EUR:
        return amount / cny_per_eur
    if source == EUR and target == CNY:
        return amount * cny_per_eur
    raise ValueError(f"unsupported currency conversion: {source_currency} -> {target_currency}")


def net_sale_value_eur(
    gross_sale_price: Decimal,
    *,
    sale_platform: str,
    sale_currency: str,
    config: MarketEconomicsConfig,
) -> Decimal:
    """Apply platform sale factor and return net sale value in EUR."""

    gross_eur = convert_currency(
        gross_sale_price,
        source_currency=sale_currency,
        target_currency=EUR,
        cny_per_eur=config.cny_per_eur,
    )
    return gross_eur * _sale_fee_factor(sale_platform, config)


def buy_value_eur(
    buy_price: Decimal,
    *,
    buy_currency: str,
    config: MarketEconomicsConfig,
) -> Decimal:
    """Return the purchase cost in EUR without sale-side fees."""

    return convert_currency(
        buy_price,
        source_currency=buy_currency,
        target_currency=EUR,
        cny_per_eur=config.cny_per_eur,
    )


def calculate_trade_result(
    *,
    buy_price: Decimal,
    buy_currency: str,
    sell_price: Decimal,
    sell_currency: str,
    sell_platform: str,
    config: MarketEconomicsConfig,
) -> EconomicResult:
    """Calculate realized profit and return for a completed trade."""

    buy_eur = buy_value_eur(buy_price, buy_currency=buy_currency, config=config)
    sell_eur = net_sale_value_eur(
        sell_price,
        sale_platform=sell_platform,
        sale_currency=sell_currency,
        config=config,
    )
    profit = sell_eur - buy_eur
    return EconomicResult(
        buy_price_eur=buy_eur,
        sell_price_eur=sell_eur,
        realized_profit_eur=profit,
        return_ratio=return_ratio(profit, buy_eur),
    )


def return_ratio(profit: Decimal, invested: Decimal) -> Decimal:
    if invested == 0:
        return Decimal("0")
    return profit / invested


def unlock_date(purchased_at: date, *, config: MarketEconomicsConfig) -> date:
    return purchased_at + timedelta(days=config.trade_hold_days)


def position_status(
    *,
    purchased_at: date,
    sold_at: date | None,
    as_of: date,
    config: MarketEconomicsConfig,
) -> PositionStatus:
    if sold_at is not None:
        return PositionStatus.CLOSED
    if unlock_date(purchased_at, config=config) > as_of:
        return PositionStatus.LOCKED
    return PositionStatus.OPEN


def effective_cash_value(
    amount: Decimal,
    *,
    platform: str,
    config: MarketEconomicsConfig,
) -> Decimal:
    """Value platform balance as cash-equivalent EUR using workbook assumptions."""

    _require_non_negative(amount, "amount")
    if platform.upper() == STEAM:
        return amount * config.steam_cash_factor
    return amount


def steam_balance_cost_factor(
    config: MarketEconomicsConfig,
    *,
    optimistic: bool = False,
) -> Decimal:
    """Return the workbook's Steam balance conversion factor.

    The calculators use `0.87 * 0.8` and `0.87 * 0.9` variants.
    """

    cash_factor = Decimal("0.9") if optimistic else config.steam_cash_factor
    return config.steam_balance_discount * cash_factor


def _sale_fee_factor(platform: str, config: MarketEconomicsConfig) -> Decimal:
    key = platform.upper()
    try:
        return config.sale_fee_factors[key]
    except KeyError as exc:
        raise ValueError(f"missing sale fee factor for platform {platform}") from exc


def _require_non_negative(value: Decimal, field_name: str) -> None:
    if value < 0:
        raise ValueError(f"{field_name} must be non-negative")

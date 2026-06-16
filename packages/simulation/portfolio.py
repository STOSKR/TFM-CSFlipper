"""Portfolio simulator with trade hold and platform fees."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import date
from decimal import Decimal
from types import MappingProxyType
from typing import Any

from packages.simulation.economics import (
    MarketEconomicsConfig,
    PositionStatus,
    buy_value_eur,
    convert_currency,
    default_excel_economics_config,
    net_sale_value_eur,
    position_status,
    return_ratio,
    unlock_date,
)


class PortfolioError(RuntimeError):
    """Base error for invalid simulated portfolio operations."""


class InsufficientCapitalError(PortfolioError):
    """Raised when a purchase would exceed available cash."""


class UnknownPositionError(PortfolioError):
    """Raised when a position id is not known by the simulator."""


class PositionNotSellableError(PortfolioError):
    """Raised when trying to sell a locked or closed position."""


@dataclass(frozen=True, slots=True)
class MarketMark:
    gross_sale_price: Decimal
    sale_currency: str
    sale_platform: str
    available_quantity: int | None = None


@dataclass(frozen=True, slots=True)
class PortfolioPosition:
    position_id: str
    item_id: str
    item_name: str
    quantity: int
    buy_platform: str
    buy_price: Decimal
    buy_currency: str
    buy_price_eur: Decimal
    invested_eur: Decimal
    purchased_at: date
    unlock_at: date
    metadata: MappingProxyType[str, Any] = field(default_factory=lambda: MappingProxyType({}))
    sold_at: date | None = None
    sell_platform: str | None = None
    sell_price: Decimal | None = None
    sell_currency: str | None = None
    gross_sale_value_eur: Decimal | None = None
    net_sale_value_eur: Decimal | None = None
    realized_profit_eur: Decimal | None = None
    realized_return: Decimal | None = None

    def status(self, as_of: date, *, config: MarketEconomicsConfig) -> PositionStatus:
        return position_status(
            purchased_at=self.purchased_at,
            sold_at=self.sold_at,
            as_of=as_of,
            config=config,
        )

    @property
    def is_closed(self) -> bool:
        return self.sold_at is not None


@dataclass(frozen=True, slots=True)
class PortfolioMetrics:
    as_of: date
    initial_cash_eur: Decimal
    cash_available_eur: Decimal
    capital_blocked_eur: Decimal
    open_invested_eur: Decimal
    realized_profit_eur: Decimal
    unrealized_profit_eur: Decimal
    equity_eur: Decimal
    peak_equity_eur: Decimal
    drawdown_eur: Decimal
    drawdown_ratio: Decimal
    locked_positions: int
    open_positions: int
    closed_positions: int


class PortfolioSimulator:
    """Deterministic portfolio accounting for historical market simulations."""

    def __init__(
        self,
        *,
        initial_cash_eur: Decimal,
        config: MarketEconomicsConfig | None = None,
    ) -> None:
        _require_non_negative(initial_cash_eur, "initial_cash_eur")
        self._config = config or default_excel_economics_config()
        self._initial_cash_eur = initial_cash_eur
        self._cash_available_eur = initial_cash_eur
        self._realized_profit_eur = Decimal("0")
        self._peak_equity_eur = initial_cash_eur
        self._next_position_number = 1
        self._positions: dict[str, PortfolioPosition] = {}

    @property
    def config(self) -> MarketEconomicsConfig:
        return self._config

    @property
    def cash_available_eur(self) -> Decimal:
        return self._cash_available_eur

    @property
    def positions(self) -> tuple[PortfolioPosition, ...]:
        return tuple(self._positions.values())

    def buy(
        self,
        *,
        item_id: str,
        item_name: str,
        buy_platform: str,
        buy_price: Decimal,
        buy_currency: str,
        purchased_at: date,
        quantity: int = 1,
        position_id: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> PortfolioPosition:
        _require_text(item_id, "item_id")
        _require_text(item_name, "item_name")
        _require_text(buy_platform, "buy_platform")
        _require_text(buy_currency, "buy_currency")
        _require_positive_decimal(buy_price, "buy_price")
        _require_positive_int(quantity, "quantity")

        buy_price_eur = buy_value_eur(
            buy_price,
            buy_currency=buy_currency,
            config=self._config,
        )
        invested_eur = buy_price_eur * Decimal(quantity)
        if invested_eur > self._cash_available_eur:
            raise InsufficientCapitalError(
                f"purchase requires {invested_eur} EUR but only "
                f"{self._cash_available_eur} EUR is available"
            )

        resolved_position_id = position_id or self._allocate_position_id()
        if resolved_position_id in self._positions:
            raise PortfolioError(f"position_id already exists: {resolved_position_id}")

        position = PortfolioPosition(
            position_id=resolved_position_id,
            item_id=item_id,
            item_name=item_name,
            quantity=quantity,
            buy_platform=buy_platform.upper(),
            buy_price=buy_price,
            buy_currency=buy_currency.upper(),
            buy_price_eur=buy_price_eur,
            invested_eur=invested_eur,
            purchased_at=purchased_at,
            unlock_at=unlock_date(purchased_at, config=self._config),
            metadata=MappingProxyType(dict(metadata or {})),
        )
        self._positions[position.position_id] = position
        self._cash_available_eur -= invested_eur
        return position

    def sell(
        self,
        position_id: str,
        *,
        sold_at: date,
        sell_platform: str,
        sell_price: Decimal,
        sell_currency: str,
        available_quantity: int | None = None,
    ) -> PortfolioPosition:
        position = self._position(position_id)
        if position.is_closed:
            raise PositionNotSellableError(f"position is already closed: {position_id}")
        if sold_at < position.purchased_at:
            raise PositionNotSellableError("sold_at cannot be before purchased_at")
        if position.status(sold_at, config=self._config) == PositionStatus.LOCKED:
            raise PositionNotSellableError(
                f"position {position_id} is locked until {position.unlock_at.isoformat()}"
            )

        _require_text(sell_platform, "sell_platform")
        _require_text(sell_currency, "sell_currency")
        _require_positive_decimal(sell_price, "sell_price")
        if available_quantity is not None and available_quantity < position.quantity:
            raise PositionNotSellableError(
                f"position {position_id} requires {position.quantity} units but only "
                f"{available_quantity} are liquid"
            )

        gross_sale_value_eur = convert_currency(
            sell_price,
            source_currency=sell_currency,
            target_currency="EUR",
            cny_per_eur=self._config.cny_per_eur,
        ) * Decimal(position.quantity)
        net_value_eur = net_sale_value_eur(
            sell_price,
            sale_platform=sell_platform,
            sale_currency=sell_currency,
            config=self._config,
        ) * Decimal(position.quantity)
        realized_profit_eur = net_value_eur - position.invested_eur
        closed_position = replace(
            position,
            sold_at=sold_at,
            sell_platform=sell_platform.upper(),
            sell_price=sell_price,
            sell_currency=sell_currency.upper(),
            gross_sale_value_eur=gross_sale_value_eur,
            net_sale_value_eur=net_value_eur,
            realized_profit_eur=realized_profit_eur,
            realized_return=return_ratio(realized_profit_eur, position.invested_eur),
        )
        self._positions[position_id] = closed_position
        self._cash_available_eur += net_value_eur
        self._realized_profit_eur += realized_profit_eur
        self._update_peak_equity(sold_at, marks={})
        return closed_position

    def metrics(
        self,
        *,
        as_of: date,
        marks: Mapping[str, MarketMark] | None = None,
    ) -> PortfolioMetrics:
        resolved_marks = dict(marks or {})
        open_value_eur = Decimal("0")
        open_invested_eur = Decimal("0")
        blocked_eur = Decimal("0")
        unrealized_profit_eur = Decimal("0")
        locked_positions = 0
        open_positions = 0
        closed_positions = 0

        for position in self._positions.values():
            status = position.status(as_of, config=self._config)
            if status == PositionStatus.CLOSED:
                closed_positions += 1
                continue

            open_positions += 1
            open_invested_eur += position.invested_eur
            if status == PositionStatus.LOCKED:
                locked_positions += 1
                blocked_eur += position.invested_eur

            marked_value_eur = self._marked_position_value(position, resolved_marks)
            open_value_eur += marked_value_eur
            unrealized_profit_eur += marked_value_eur - position.invested_eur

        equity_eur = self._cash_available_eur + open_value_eur
        if equity_eur > self._peak_equity_eur:
            self._peak_equity_eur = equity_eur
        drawdown_eur = max(Decimal("0"), self._peak_equity_eur - equity_eur)
        return PortfolioMetrics(
            as_of=as_of,
            initial_cash_eur=self._initial_cash_eur,
            cash_available_eur=self._cash_available_eur,
            capital_blocked_eur=blocked_eur,
            open_invested_eur=open_invested_eur,
            realized_profit_eur=self._realized_profit_eur,
            unrealized_profit_eur=unrealized_profit_eur,
            equity_eur=equity_eur,
            peak_equity_eur=self._peak_equity_eur,
            drawdown_eur=drawdown_eur,
            drawdown_ratio=return_ratio(drawdown_eur, self._peak_equity_eur),
            locked_positions=locked_positions,
            open_positions=open_positions,
            closed_positions=closed_positions,
        )

    def _allocate_position_id(self) -> str:
        position_id = f"pos-{self._next_position_number}"
        self._next_position_number += 1
        return position_id

    def _position(self, position_id: str) -> PortfolioPosition:
        try:
            return self._positions[position_id]
        except KeyError as exc:
            raise UnknownPositionError(f"unknown position_id: {position_id}") from exc

    def _marked_position_value(
        self,
        position: PortfolioPosition,
        marks: Mapping[str, MarketMark],
    ) -> Decimal:
        mark = marks.get(position.position_id)
        if mark is None:
            return position.invested_eur
        _require_positive_decimal(mark.gross_sale_price, "gross_sale_price")
        return net_sale_value_eur(
            mark.gross_sale_price,
            sale_platform=mark.sale_platform,
            sale_currency=mark.sale_currency,
            config=self._config,
        ) * Decimal(position.quantity)

    def _update_peak_equity(
        self,
        as_of: date,
        *,
        marks: Mapping[str, MarketMark],
    ) -> None:
        self.metrics(as_of=as_of, marks=marks)


def _require_text(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} cannot be empty")


def _require_positive_decimal(value: Decimal, field_name: str) -> None:
    if value <= 0:
        raise ValueError(f"{field_name} must be greater than zero")


def _require_non_negative(value: Decimal, field_name: str) -> None:
    if value < 0:
        raise ValueError(f"{field_name} must be non-negative")


def _require_positive_int(value: int, field_name: str) -> None:
    if value <= 0:
        raise ValueError(f"{field_name} must be greater than zero")

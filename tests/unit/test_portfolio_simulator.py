from datetime import date
from decimal import Decimal

import pytest

from packages.simulation import (
    BUFF,
    STEAM,
    InsufficientCapitalError,
    MarketMark,
    PortfolioSimulator,
    PositionNotSellableError,
    PositionStatus,
    UnknownPositionError,
    default_excel_economics_config,
)


def test_buy_creates_locked_position_and_blocks_capital() -> None:
    simulator = PortfolioSimulator(
        initial_cash_eur=Decimal("100"),
        config=default_excel_economics_config(cny_per_eur=Decimal("8"), trade_hold_days=8),
    )

    position = simulator.buy(
        item_id="item-1",
        item_name="AK-47 | Slate",
        buy_platform=BUFF,
        buy_price=Decimal("80"),
        buy_currency="CNY",
        purchased_at=date(2026, 1, 1),
    )
    metrics = simulator.metrics(as_of=date(2026, 1, 2))

    assert position.position_id == "pos-1"
    assert position.invested_eur == Decimal("10")
    assert position.unlock_at == date(2026, 1, 9)
    assert position.status(date(2026, 1, 2), config=simulator.config) == PositionStatus.LOCKED
    assert simulator.cash_available_eur == Decimal("90")
    assert metrics.cash_available_eur == Decimal("90")
    assert metrics.capital_blocked_eur == Decimal("10")
    assert metrics.open_invested_eur == Decimal("10")
    assert metrics.equity_eur == Decimal("100")
    assert metrics.locked_positions == 1
    assert metrics.open_positions == 1
    assert metrics.closed_positions == 0


def test_position_cannot_be_sold_before_trade_hold_unlock() -> None:
    simulator = PortfolioSimulator(initial_cash_eur=Decimal("100"))
    position = simulator.buy(
        item_id="item-1",
        item_name="AK-47 | Slate",
        buy_platform=BUFF,
        buy_price=Decimal("80"),
        buy_currency="CNY",
        purchased_at=date(2026, 1, 1),
    )

    with pytest.raises(PositionNotSellableError, match="locked until 2026-01-09"):
        simulator.sell(
            position.position_id,
            sold_at=date(2026, 1, 8),
            sell_platform=STEAM,
            sell_price=Decimal("20"),
            sell_currency="EUR",
        )


def test_sell_after_unlock_realizes_net_profit_and_releases_cash() -> None:
    simulator = PortfolioSimulator(initial_cash_eur=Decimal("100"))
    position = simulator.buy(
        item_id="item-1",
        item_name="AK-47 | Slate",
        buy_platform=BUFF,
        buy_price=Decimal("80"),
        buy_currency="CNY",
        purchased_at=date(2026, 1, 1),
    )

    closed = simulator.sell(
        position.position_id,
        sold_at=date(2026, 1, 9),
        sell_platform=STEAM,
        sell_price=Decimal("20"),
        sell_currency="EUR",
    )
    metrics = simulator.metrics(as_of=date(2026, 1, 9))

    assert closed.status(date(2026, 1, 9), config=simulator.config) == PositionStatus.CLOSED
    assert closed.gross_sale_value_eur == Decimal("20")
    assert closed.net_sale_value_eur == Decimal("17.40")
    assert closed.realized_profit_eur == Decimal("7.40")
    assert closed.realized_return == Decimal("0.740")
    assert simulator.cash_available_eur == Decimal("107.40")
    assert metrics.realized_profit_eur == Decimal("7.40")
    assert metrics.capital_blocked_eur == Decimal("0")
    assert metrics.open_positions == 0
    assert metrics.closed_positions == 1


def test_sell_rejects_insufficient_liquidity() -> None:
    simulator = PortfolioSimulator(initial_cash_eur=Decimal("100"))
    position = simulator.buy(
        item_id="item-1",
        item_name="AK-47 | Slate",
        buy_platform=BUFF,
        buy_price=Decimal("80"),
        buy_currency="CNY",
        purchased_at=date(2026, 1, 1),
        quantity=2,
    )

    with pytest.raises(PositionNotSellableError, match="only 1 are liquid"):
        simulator.sell(
            position.position_id,
            sold_at=date(2026, 1, 9),
            sell_platform=STEAM,
            sell_price=Decimal("20"),
            sell_currency="EUR",
            available_quantity=1,
        )


def test_metrics_use_marks_for_unrealized_profit_and_drawdown() -> None:
    simulator = PortfolioSimulator(initial_cash_eur=Decimal("100"))
    position = simulator.buy(
        item_id="item-1",
        item_name="AK-47 | Slate",
        buy_platform=STEAM,
        buy_price=Decimal("20"),
        buy_currency="EUR",
        purchased_at=date(2026, 1, 1),
    )

    loss_metrics = simulator.metrics(
        as_of=date(2026, 1, 9),
        marks={
            position.position_id: MarketMark(
                gross_sale_price=Decimal("10"),
                sale_currency="EUR",
                sale_platform=STEAM,
            )
        },
    )
    gain_metrics = simulator.metrics(
        as_of=date(2026, 1, 10),
        marks={
            position.position_id: MarketMark(
                gross_sale_price=Decimal("30"),
                sale_currency="EUR",
                sale_platform=STEAM,
            )
        },
    )
    later_metrics = simulator.metrics(
        as_of=date(2026, 1, 11),
        marks={
            position.position_id: MarketMark(
                gross_sale_price=Decimal("25"),
                sale_currency="EUR",
                sale_platform=STEAM,
            )
        },
    )

    assert loss_metrics.equity_eur == Decimal("88.70")
    assert loss_metrics.unrealized_profit_eur == Decimal("-11.30")
    assert loss_metrics.drawdown_eur == Decimal("11.30")
    assert gain_metrics.equity_eur == Decimal("106.10")
    assert gain_metrics.peak_equity_eur == Decimal("106.10")
    assert later_metrics.equity_eur == Decimal("101.75")
    assert later_metrics.drawdown_eur == Decimal("4.35")


def test_buy_rejects_insufficient_capital() -> None:
    simulator = PortfolioSimulator(initial_cash_eur=Decimal("5"))

    with pytest.raises(InsufficientCapitalError, match="requires 10"):
        simulator.buy(
            item_id="item-1",
            item_name="AK-47 | Slate",
            buy_platform=BUFF,
            buy_price=Decimal("80"),
            buy_currency="CNY",
            purchased_at=date(2026, 1, 1),
        )


def test_sell_rejects_unknown_position() -> None:
    simulator = PortfolioSimulator(initial_cash_eur=Decimal("100"))

    with pytest.raises(UnknownPositionError, match="missing"):
        simulator.sell(
            "missing",
            sold_at=date(2026, 1, 9),
            sell_platform=STEAM,
            sell_price=Decimal("20"),
            sell_currency="EUR",
        )

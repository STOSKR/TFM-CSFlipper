import pytest

from apps.acquisition.buff163_market import (
    Buff163Connector,
    extract_buff_buy_orders,
    extract_buff_price_text,
)


def test_extract_buff_price_text_prefers_price_lines() -> None:
    body_text = """
    AK-47 | Slate
    Reference ¥ 10.20
    Selling price ¥ 12.34
    """

    assert extract_buff_price_text(body_text) == "¥ 12.34"


def test_extract_buff_price_text_falls_back_to_first_money_value() -> None:
    body_text = "AK-47 | Slate\nSome section\n￥12.34"

    assert extract_buff_price_text(body_text) == "￥12.34"


def test_extract_buff_buy_orders_from_labelled_rows() -> None:
    buy_orders = extract_buff_buy_orders(
        [
            {"className": "buy-order", "text": "Buy order CNY 12.34 5"},
            {"className": "selling", "text": "Sell listing CNY 13.00 1"},
            {"className": "demand-list", "text": "Demand CNY 12.10 18"},
        ]
    )

    assert buy_orders == (
        {"price": "CNY 12.34", "quantity": 5},
        {"price": "CNY 12.10", "quantity": 18},
    )


@pytest.mark.asyncio
async def test_buff_connector_lenient_empty_candidates() -> None:
    observations, errors = await Buff163Connector().fetch_candidates_lenient(
        [],
        correlation_id="test",
    )

    assert observations == ()
    assert errors == ()

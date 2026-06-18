import pytest

from apps.acquisition.buff163_market import (
    Buff163Connector,
    extract_buff_api_buy_orders,
    extract_buff_buy_orders,
    extract_buff_price_history,
    extract_buff_price_text,
    extract_buff_recent_sales,
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


def test_extract_buff_buy_orders_filters_concatenated_noise() -> None:
    buy_orders = extract_buff_buy_orders(
        [
            {
                "className": "buy-order-list",
                "text": "Buy order ¥ 819.5 10456 57276831659 ¥ 820 ¥ 820 10462",
            },
        ]
    )

    assert buy_orders == (
        {"price": "¥ 819.5", "quantity": 10456},
        {"price": "¥ 820", "quantity": 10462},
    )


def test_extract_buff_buy_orders_keeps_display_currency_only() -> None:
    buy_orders = extract_buff_buy_orders(
        [
            {
                "className": "buy-order-list",
                "text": "Buy order ¥ 200 2554 € 25.54 40 103 ¥ 20086 ¥ 200.86 2565",
            },
        ],
        display_currency="CNY",
    )

    assert buy_orders == (
        {"price": "¥ 200", "quantity": 2554},
        {"price": "¥ 200.86", "quantity": 2565},
    )


def test_extract_buff_api_buy_orders_keeps_individual_orders() -> None:
    buy_orders = extract_buff_api_buy_orders(
        {
            "code": "OK",
            "data": {
                "items": [
                    {
                        "id": "260614T1",
                        "user_id": "U1",
                        "price": "429",
                        "num": 1,
                        "created_at": 1781395233,
                    },
                    {
                        "id": "260614T2",
                        "user_id": "U2",
                        "price": "429",
                        "num": 1,
                        "created_at": 1781395458,
                    },
                    {"id": "260614T3", "price": "428", "num": 8},
                ],
            },
        }
    )

    assert buy_orders[:2] == (
        {
            "source": "buff_buy_order",
            "price": "CNY 429",
            "quantity": 1,
            "order_id": "260614T1",
            "buyer_id": "U1",
            "created_at": "2026-06-14T00:00:33+00:00",
        },
        {
            "source": "buff_buy_order",
            "price": "CNY 429",
            "quantity": 1,
            "order_id": "260614T2",
            "buyer_id": "U2",
            "created_at": "2026-06-14T00:04:18+00:00",
        },
    )
    assert buy_orders[2] == {
        "source": "buff_buy_order",
        "price": "CNY 428",
        "quantity": 8,
        "order_id": "260614T3",
    }


def test_extract_buff_recent_sales_from_bill_order_payload() -> None:
    recent_sales = extract_buff_recent_sales(
        {
            "code": "OK",
            "data": {
                "items": [
                    {
                        "price": "459",
                        "buyer_pay_time": 1781366400,
                        "asset_info": {"assetid": "52142244274"},
                    },
                ],
            },
        }
    )

    assert recent_sales == (
        {
            "source": "buff_bill_order",
            "price": "CNY 459",
            "sold_at": "2026-06-13T16:00:00+00:00",
            "asset_id": "52142244274",
        },
    )


def test_extract_buff_price_history_v2_splits_three_series() -> None:
    history = extract_buff_price_history(
        {
            "code": "OK",
            "data": {
                "price_history": [[1781366400000, "459.5"]],
                "buy_order_price_history": [[1781366400000, "450.25"]],
                "sell_order_count_history": [[1781366400000, 33]],
            },
        }
    )

    assert history == (
        {
            "source": "buff_price_history_v2",
            "observed_at": "2026-06-13T16:00:00+00:00",
            "currency": "CNY",
            "buff_sell_price": "459.5",
            "buff_buy_order_price": "450.25",
            "buff_listing_count": 33,
        },
    )


def test_extract_buff_price_history_v2_reads_buff_lines_payload() -> None:
    history = extract_buff_price_history(
        {
            "code": "OK",
            "data": {
                "lines": [
                    {
                        "key": "sell_min_price_history",
                        "name": "在售最低",
                        "points": [[1781366400000, "459.5"]],
                    },
                    {
                        "key": "buy_order_price_history",
                        "name": "求购最高",
                        "points": [[1781366400000, "450.25"]],
                    },
                    {
                        "key": "sell_order_count_history",
                        "name": "在售数量",
                        "points": [[1781366400000, 33]],
                    },
                ],
            },
        }
    )

    assert history == (
        {
            "source": "buff_price_history_v2",
            "observed_at": "2026-06-13T16:00:00+00:00",
            "currency": "CNY",
            "buff_sell_price": "459.5",
            "buff_buy_order_price": "450.25",
            "buff_listing_count": 33,
        },
    )


@pytest.mark.asyncio
async def test_buff_connector_lenient_empty_candidates() -> None:
    observations, errors = await Buff163Connector().fetch_candidates_lenient(
        [],
        correlation_id="test",
    )

    assert observations == ()
    assert errors == ()

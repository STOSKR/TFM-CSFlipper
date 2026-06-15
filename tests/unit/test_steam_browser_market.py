from apps.acquisition.steam_browser_market import (
    _select_chart_range,
    extract_steam_buy_orders,
    extract_steam_orderbook_buy_orders,
    extract_steam_price_text,
    extract_steam_recent_sales,
)


def test_extract_steam_price_text_prefers_selector_text() -> None:
    debug_log: list[str] = []

    price = extract_steam_price_text(
        [{"selector": ".market_listing_price", "text": "Starting at: 12,34\u20ac"}],
        "body without price",
        debug_log=debug_log,
    )

    assert price == "12,34\u20ac"
    assert "selector" in debug_log[0]


def test_extract_steam_price_text_uses_new_quality_card_normal_price() -> None:
    debug_log: list[str] = []

    price = extract_steam_price_text(
        [{"text": "Factory New\n\u00a5 545.33\n\u00a5 106.34"}],
        "Wallet \u00a50.00 Factory New \u00a5 545.33 \u00a5 106.34",
        quality="Factory New",
        stattrak=False,
        debug_log=debug_log,
    )

    assert price == "\u00a5 545.33"
    assert "quality card" in debug_log[0]


def test_extract_steam_price_text_uses_new_quality_card_stattrak_price() -> None:
    price = extract_steam_price_text(
        [{"text": "Factory New\n\u00a5 545.33\n\u00a5 106.34"}],
        "Wallet \u00a50.00 Factory New \u00a5 545.33 \u00a5 106.34",
        quality="Factory New",
        stattrak=True,
    )

    assert price == "\u00a5 106.34"


def test_extract_steam_price_text_prefers_new_market_ssr_bucket() -> None:
    price = extract_steam_price_text(
        [],
        "Wallet \u20ac0,00\nField-Tested\n\u20ac5,41\n\u20ac17,45",
        quality="Field-Tested",
        stattrak=True,
        market_hash_name="StatTrak AK-47 | Slate (Field-Tested)",
        ssr_loader_data=[
            '{"success":true,"appid":730,"buckets":['
            '{"bucket_id":"AK-47 | Slate (Field-Tested)",'
            '"localized_name_inside_group":"Field-Tested","strPrice":"\u20ac5,41"},'
            '{"bucket_id":"StatTrak\u2122 AK-47 | Slate (Field-Tested)",'
            '"localized_name_inside_group":"StatTrak\u2122 Field-Tested","strPrice":"\u20ac17,45"}'
            "]}",
        ],
    )

    assert price == "\u20ac17,45"


def test_extract_steam_price_text_uses_body_quality_block() -> None:
    price = extract_steam_price_text(
        [],
        "Wallet \u20ac0,00\nFactory New\n\u20ac21,00\n\u20ac84,00\n"
        "Minimal Wear\n\u20ac12,00\n\u20ac45,00",
        quality="Minimal Wear",
        stattrak=False,
    )

    assert price == "\u20ac12,00"


def test_extract_steam_price_text_handles_pln_prices() -> None:
    price = extract_steam_price_text(
        [{"text": "Field-Tested\n22,90 z\u0142\n67,32 z\u0142"}],
        "",
        quality="Field-Tested",
        stattrak=False,
    )

    assert price == "22,90 z\u0142"


def test_extract_steam_price_text_uses_fallback_line() -> None:
    price = extract_steam_price_text(
        [],
        "Other text\nStarting at: 12.34 EUR\nMore text",
    )

    assert price == "12.34 EUR"


def test_extract_steam_buy_orders_from_table_rows() -> None:
    buy_orders = extract_steam_buy_orders(
        [
            ["Price", "Quantity"],
            ["12,34\u20ac", "5"],
            ["11,90\u20ac", "18"],
        ]
    )

    assert buy_orders == (
        {"price": "12,34\u20ac", "quantity": 5},
        {"price": "11,90\u20ac", "quantity": 18},
    )


def test_extract_steam_orderbook_buy_orders_from_compact_api_payload() -> None:
    buy_orders = extract_steam_orderbook_buy_orders(
        {
            "success": True,
            "data": {
                "rgCompactBuyOrders": [61206, 2, 61197, 1],
            },
        },
        currency="CNY",
    )

    assert buy_orders == (
        {"source": "steam_orderbook", "price": "CNY 612.06", "quantity": 2},
        {"source": "steam_orderbook", "price": "CNY 611.97", "quantity": 1},
    )


def test_extract_steam_recent_sales_from_recharts_payload() -> None:
    recent_sales = extract_steam_recent_sales(
        {
            "selected_range": "Month",
            "price_line_path": "M10,90L20,50L30,10",
            "price_ticks": [
                {"text": "EUR 100.00", "y": 0},
                {"text": "EUR 0.00", "y": 100},
            ],
            "time_ticks": [
                {"text": "6/1/2026, 1 PM", "x": 10},
                {"text": "6/2/2026, 1 PM", "x": 20},
                {"text": "6/3/2026, 1 PM", "x": 30},
            ],
        },
        limit=2,
    )

    assert recent_sales == (
        {
            "source": "steam_recharts",
            "granularity": "point",
            "point_index": 1,
            "price": "50.00",
            "time_label": "6/2/2026, 1 PM",
            "observed_at": "2026-06-02T13:00:00+00:00",
            "range": "Month",
        },
        {
            "source": "steam_recharts",
            "granularity": "point",
            "point_index": 2,
            "price": "90.00",
            "time_label": "6/3/2026, 1 PM",
            "observed_at": "2026-06-03T13:00:00+00:00",
            "range": "Month",
        },
    )


def test_extract_steam_recent_sales_uses_quality_curve_and_all_points() -> None:
    recent_sales = extract_steam_recent_sales(
        {
            "selected_range": "Week",
            "price_line_paths": [
                "M10,90L20,90",
                "M10,70L20,70",
                "M10,50L20,50",
            ],
            "price_ticks": [
                {"text": "EUR 100.00", "y": 0},
                {"text": "EUR 0.00", "y": 100},
            ],
            "time_ticks": [
                {"text": "6/1/2026, 1 PM", "x": 10},
                {"text": "6/1/2026, 3 PM", "x": 20},
            ],
        },
        quality="Field-Tested",
        limit=None,
    )

    assert recent_sales == (
        {
            "source": "steam_recharts",
            "granularity": "point",
            "point_index": 0,
            "price": "50.00",
            "time_label": "6/1/2026, 1 PM",
            "observed_at": "2026-06-01T13:00:00+00:00",
            "range": "Week",
        },
        {
            "source": "steam_recharts",
            "granularity": "point",
            "point_index": 1,
            "price": "50.00",
            "time_label": "6/1/2026, 3 PM",
            "observed_at": "2026-06-01T15:00:00+00:00",
            "range": "Week",
        },
    )


def test_extract_steam_recent_sales_interpolates_date_only_ticks_per_point() -> None:
    recent_sales = extract_steam_recent_sales(
        {
            "selected_range": "Lifetime",
            "price_line_path": "M10,90L10.2,80L20,50",
            "price_ticks": [
                {"text": "EUR 100.00", "y": 0},
                {"text": "EUR 0.00", "y": 100},
            ],
            "time_ticks": [
                {"text": "6/1/2026", "x": 10},
                {"text": "6/2/2026", "x": 20},
            ],
        },
        limit=None,
    )

    assert [row["observed_at"] for row in recent_sales] == [
        "2026-06-01T00:00:00+00:00",
        "2026-06-01T01:00:00+00:00",
        "2026-06-02T00:00:00+00:00",
    ]
    assert [row["time_label"] for row in recent_sales] == [
        "6/1/2026, 12 AM",
        "6/1/2026, 1 AM",
        "6/2/2026, 12 AM",
    ]


async def test_select_chart_range_requests_lifetime() -> None:
    page = FakeRangePage()
    debug_log: list[str] = []

    await _select_chart_range(page, range_label="Lifetime", debug_log=debug_log)

    assert page.requested_range == "Lifetime"
    assert "alreadySelected" in debug_log[0]


class FakeRangePage:
    requested_range: str | None = None

    async def evaluate(self, _script: str, range_label: str) -> dict[str, bool]:
        self.requested_range = range_label
        return {"clicked": False, "alreadySelected": True}

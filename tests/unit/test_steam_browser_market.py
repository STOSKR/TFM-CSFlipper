from apps.acquisition.steam_browser_market import (
    extract_steam_buy_orders,
    extract_steam_price_text,
)


def test_extract_steam_price_text_prefers_selector_text() -> None:
    debug_log: list[str] = []

    price = extract_steam_price_text(
        [{"selector": ".market_listing_price", "text": "Starting at: 12,34€"}],
        "body without price",
        debug_log=debug_log,
    )

    assert price == "12,34€"
    assert "selector" in debug_log[0]


def test_extract_steam_price_text_uses_new_quality_card_normal_price() -> None:
    debug_log: list[str] = []

    price = extract_steam_price_text(
        [{"text": "Factory New\n¥ 545.33\n¥ 106.34"}],
        "Wallet ¥0.00 Factory New ¥ 545.33 ¥ 106.34",
        quality="Factory New",
        stattrak=False,
        debug_log=debug_log,
    )

    assert price == "¥ 545.33"
    assert "quality card" in debug_log[0]


def test_extract_steam_price_text_uses_new_quality_card_stattrak_price() -> None:
    price = extract_steam_price_text(
        [{"text": "Factory New\n¥ 545.33\n¥ 106.34"}],
        "Wallet ¥0.00 Factory New ¥ 545.33 ¥ 106.34",
        quality="Factory New",
        stattrak=True,
    )

    assert price == "¥ 106.34"


def test_extract_steam_price_text_prefers_new_market_ssr_bucket() -> None:
    price = extract_steam_price_text(
        [],
        "Wallet €0,00\nField-Tested\n€5,41\n€17,45",
        quality="Field-Tested",
        stattrak=True,
        market_hash_name="StatTrak AK-47 | Slate (Field-Tested)",
        ssr_loader_data=[
            '{"success":true,"appid":730,"buckets":['
            '{"bucket_id":"AK-47 | Slate (Field-Tested)",'
            '"localized_name_inside_group":"Field-Tested","strPrice":"€5,41"},'
            '{"bucket_id":"StatTrak™ AK-47 | Slate (Field-Tested)",'
            '"localized_name_inside_group":"StatTrak™ Field-Tested","strPrice":"€17,45"}'
            "]}",
        ],
    )

    assert price == "€17,45"


def test_extract_steam_price_text_uses_body_quality_block() -> None:
    price = extract_steam_price_text(
        [],
        "Wallet €0,00\nFactory New\n€21,00\n€84,00\nMinimal Wear\n€12,00\n€45,00",
        quality="Minimal Wear",
        stattrak=False,
    )

    assert price == "€12,00"


def test_extract_steam_price_text_handles_pln_prices() -> None:
    price = extract_steam_price_text(
        [{"text": "Field-Tested\n22,90 zł\n67,32 zł"}],
        "",
        quality="Field-Tested",
        stattrak=False,
    )

    assert price == "22,90 zł"


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
            ["12,34€", "5"],
            ["11,90€", "18"],
        ]
    )

    assert buy_orders == (
        {"price": "12,34€", "quantity": 5},
        {"price": "11,90€", "quantity": 18},
    )

from apps.acquisition.steam_browser_market import extract_steam_price_text


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


def test_extract_steam_price_text_uses_fallback_line() -> None:
    price = extract_steam_price_text(
        [],
        "Other text\nStarting at: 12.34 EUR\nMore text",
    )

    assert price == "12.34 EUR"

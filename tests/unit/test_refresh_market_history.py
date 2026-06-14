from apps.cli.refresh_market_history import candidate_from_market_item_row


def test_candidate_from_market_item_row_reuses_stored_platform_urls() -> None:
    candidate = candidate_from_market_item_row(
        {
            "name": "AK-47 | Slate",
            "quality": "Field-Tested",
            "stattrak": True,
            "steam_url": "https://steamcommunity.com/market/listings/730/StatTrak",
            "buff_url": "https://buff.163.com/goods/123",
        }
    )

    assert candidate.item_name == "AK-47 | Slate"
    assert candidate.market_hash_name == "AK-47 | Slate (Field-Tested)"
    assert candidate.quality == "Field-Tested"
    assert candidate.stattrak is True
    assert candidate.steam_url == "https://steamcommunity.com/market/listings/730/StatTrak"
    assert candidate.buff_url == "https://buff.163.com/goods/123"

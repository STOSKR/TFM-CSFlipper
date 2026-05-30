from decimal import Decimal

from apps.acquisition.steamdt_hanging import parse_steamdt_rows


def test_parse_steamdt_hanging_row_extracts_candidate() -> None:
    rows = [
        {
            "cells": [
                "1",
                "StatTrak AK-47 | Slate (Field-Tested)",
                "BUFF 12,10 EUR",
                "Steam 14,61 EUR",
                "2,51 EUR",
                "Volume 42",
                "61,54%",
            ],
            "links": [
                "https://www.steamdt.com/item/ak-slate",
                "https://buff.163.com/goods/875627",
                "https://steamcommunity.com/market/listings/730/"
                "StatTrak%20AK-47%20%7C%20Slate%20(Field-Tested)",
            ],
        }
    ]

    candidates = parse_steamdt_rows(rows)

    assert len(candidates) == 1
    assert candidates[0].item_name == "StatTrak AK-47 | Slate"
    assert candidates[0].market_hash_name == "StatTrak AK-47 | Slate (Field-Tested)"
    assert candidates[0].quality == "Field-Tested"
    assert candidates[0].stattrak is True
    assert candidates[0].currency == "EUR"
    assert candidates[0].buff_price == Decimal("12.10")
    assert candidates[0].steam_price == Decimal("14.61")
    assert candidates[0].profit == Decimal("2.51")
    assert candidates[0].profitability_percent == Decimal("61.54")
    assert candidates[0].volume == 42


def test_parse_steamdt_hanging_row_prefers_steam_url_identity() -> None:
    rows = [
        {
            "cells": [
                "",
                "localized item name",
                "Y3.57 39 minutes ago",
                "Y23.83 1 hour ago",
                "Y20.73",
                "36",
            ],
            "links": [
                "https://steamcommunity.com/market/listings/730/"
                "Nova%20%7C%20Ranger%20(Minimal%20Wear)",
            ],
        }
    ]

    candidates = parse_steamdt_rows(rows)

    assert candidates[0].item_name == "Nova | Ranger"
    assert candidates[0].display_name == "localized item name"
    assert candidates[0].market_hash_name == "Nova | Ranger (Minimal Wear)"
    assert candidates[0].quality == "Minimal Wear"
    assert candidates[0].buff_price == Decimal("3.57")
    assert candidates[0].steam_price == Decimal("23.83")


def test_parse_steamdt_hanging_row_filters_non_skin_items() -> None:
    rows = [
        {"cells": ["1", "Sticker | Example", "1 EUR", "2 EUR"], "links": []},
        {"cells": ["2", "Music Kit | Example", "1 EUR", "2 EUR"], "links": []},
        {"cells": ["3", "AK-47 | Slate (Field-Tested)", "1 EUR", "2 EUR"], "links": []},
    ]

    candidates = parse_steamdt_rows(rows)

    assert len(candidates) == 1
    assert candidates[0].market_hash_name == "AK-47 | Slate (Field-Tested)"

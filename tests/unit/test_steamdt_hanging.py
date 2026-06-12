import json
from decimal import Decimal
from pathlib import Path

from apps.acquisition.steamdt_hanging import (
    SteamDTCandidate,
    SteamDTHangingFilters,
    calculate_break_even_steam_price,
    calculate_gross_profit,
    calculate_gross_roi_percent,
    calculate_net_profit,
    calculate_net_roi_percent,
    merge_candidate_links,
    parse_steamdt_rows,
    save_candidates,
)


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
    assert candidates[0].profitability_percent == Decimal("20.74380165289256198347107438")
    assert candidates[0].volume == 42


def test_parse_steamdt_hanging_row_calculates_profit_instead_of_trusting_table_cell() -> None:
    rows = [
        {
            "cells": [
                "",
                "Dual Berettas | Royal Consorts (Factory New)",
                "€55.93 40 minutes ago",
                "€58.36 an hour ago",
                "€54.53",
                "23",
                "1.07",
                "1.302",
                "Platform Data",
            ],
            "links": [
                "https://steamcommunity.com/market/listings/730/"
                "Dual%20Berettas%20%7C%20Royal%20Consorts%20(Factory%20New)",
            ],
        }
    ]

    candidates = parse_steamdt_rows(rows)

    assert candidates[0].profit == Decimal("2.43")
    assert candidates[0].profitability_percent == Decimal("4.344716610048274629000536385")
    assert candidates[0].net_profit == Decimal("-15.31144")
    assert candidates[0].net_roi_percent == Decimal("-27.37607723940640085821562668")
    assert candidates[0].break_even_steam_price == Decimal("80.35919540229885057471264368")


def test_calculate_gross_profit_and_roi_percent() -> None:
    assert calculate_gross_profit(Decimal("55.93"), Decimal("58.36")) == Decimal("2.43")
    assert calculate_gross_roi_percent(
        Decimal("55.93"),
        Decimal("58.36"),
    ) == Decimal("4.344716610048274629000536385")


def test_calculate_net_profit_roi_and_break_even_with_configured_fees() -> None:
    assert calculate_net_profit(
        Decimal("55.93"),
        Decimal("58.36"),
        steam_sale_fee_rate=Decimal("0.13"),
        withdrawal_fee_rate=Decimal("0.20"),
    ) == Decimal("-15.31144")
    assert calculate_net_roi_percent(
        Decimal("55.93"),
        Decimal("58.36"),
        steam_sale_fee_rate=Decimal("0.13"),
        withdrawal_fee_rate=Decimal("0.20"),
    ) == Decimal("-27.37607723940640085821562668")
    assert calculate_break_even_steam_price(
        Decimal("55.93"),
        steam_sale_fee_rate=Decimal("0.13"),
        withdrawal_fee_rate=Decimal("0.20"),
    ) == Decimal("80.35919540229885057471264368")


def test_steamdt_discovery_does_not_open_detail_pages_by_default() -> None:
    assert SteamDTHangingFilters().enrich_missing_platform_links is False


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


def test_parse_steamdt_hanging_market_card_row_keeps_buff_url() -> None:
    rows = [
        {
            "cells": [
                "AK-47 | Slate (Field-Tested)",
                "BUFF",
                "Y 179.38",
                "For Sale: 228",
            ],
            "links": [
                "https://buff.163.com/goods/871595?from=market#tab=selling",
                "https://steamcommunity.com/market/listings/730/"
                "AK-47%20%7C%20Slate%20(Field-Tested)",
            ],
            "market_cards": [
                {
                    "text": "BUFF\nY 179.38\nFor Sale: 228\n7 minutes ago",
                    "links": [
                        "https://buff.163.com/goods/871595?from=market#tab=selling",
                    ],
                },
                {
                    "text": "STEAM\nY 185.60\nFor Sale: 92\n10 minutes ago",
                    "links": [
                        "https://steamcommunity.com/market/listings/730/"
                        "AK-47%20%7C%20Slate%20(Field-Tested)",
                    ],
                },
            ],
        }
    ]

    candidates = parse_steamdt_rows(rows)

    assert len(candidates) == 1
    assert (
        candidates[0].buff_url
        == "https://buff.163.com/goods/871595?from=market#tab=selling"
    )
    assert candidates[0].market_hash_name == "AK-47 | Slate (Field-Tested)"
    assert candidates[0].buff_price == Decimal("179.38")
    assert candidates[0].steam_price == Decimal("185.60")
    assert candidates[0].volume == 228


def test_parse_steamdt_hanging_row_filters_non_skin_items() -> None:
    rows = [
        {"cells": ["1", "Sticker | Example", "1 EUR", "2 EUR"], "links": []},
        {"cells": ["2", "Music Kit | Example", "1 EUR", "2 EUR"], "links": []},
        {"cells": ["3", "Trapper Aggressor | Guerrilla Warfare", "1 EUR", "2 EUR"], "links": []},
        {"cells": ["3", "AK-47 | Slate (Field-Tested)", "1 EUR", "2 EUR"], "links": []},
    ]

    candidates = parse_steamdt_rows(rows)

    assert len(candidates) == 1
    assert candidates[0].market_hash_name == "AK-47 | Slate (Field-Tested)"


def test_save_candidates_creates_parent_directory(tmp_path: Path) -> None:
    output_path = tmp_path / "nested" / "steamdt_candidates.json"

    save_candidates(
        output_path,
        (
            SteamDTCandidate(
                item_name="AK-47 | Slate",
                market_hash_name="AK-47 | Slate (Field-Tested)",
                quality="Field-Tested",
                steam_price=Decimal("12.34"),
            ),
        ),
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert payload[0]["market_hash_name"] == "AK-47 | Slate (Field-Tested)"
    assert payload[0]["steam_price"] == "12.34"
    assert "raw_cells" not in payload[0]
    assert "display_name" not in payload[0]


def test_merge_candidate_links_fills_missing_buff_url_from_detail_links() -> None:
    candidate = SteamDTCandidate(
        item_name="Glock-18 | Ironwork",
        market_hash_name="Glock-18 | Ironwork (Factory New)",
        quality="Factory New",
        item_url="https://www.steamdt.com/en/item/123",
        buff_url=None,
    )

    enriched = merge_candidate_links(
        candidate,
        (
            "https://buff.163.com/goods/35031?from=market#tab=selling",
            "https://steamcommunity.com/market/listings/730/Glock-18",
        ),
    )

    assert enriched.buff_url == "https://buff.163.com/goods/35031?from=market#tab=selling"
    assert enriched.steam_url == "https://steamcommunity.com/market/listings/730/Glock-18"

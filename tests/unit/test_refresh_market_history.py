from datetime import UTC, datetime

from apps.cli.refresh_market_history import (
    buff_history_days_from_db_row,
    candidate_from_market_item_row,
)


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


def test_buff_history_days_uses_one_day_overlap_from_oldest_known_history() -> None:
    days = buff_history_days_from_db_row(
        {
            "item_count": 3,
            "latest_count": 3,
            "oldest_latest_observed_at": datetime(2026, 6, 12, 12, 0, tzinfo=UTC),
        },
        max_days=365,
        now=datetime(2026, 6, 16, 9, 0, tzinfo=UTC),
    )

    assert days == 5


def test_buff_history_days_uses_full_window_when_any_item_has_no_history() -> None:
    days = buff_history_days_from_db_row(
        {
            "item_count": 3,
            "latest_count": 2,
            "oldest_latest_observed_at": datetime(2026, 6, 12, 12, 0, tzinfo=UTC),
        },
        max_days=365,
        now=datetime(2026, 6, 16, 9, 0, tzinfo=UTC),
    )

    assert days == 365

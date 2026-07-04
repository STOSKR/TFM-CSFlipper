import os
import subprocess
import sys
from datetime import UTC, datetime
from decimal import Decimal
from inspect import getsource

from apps.acquisition.buff163_market import Buff163Observation
from apps.acquisition.platform_workers import PlatformWorkerResult, WorkerError
from apps.acquisition.steam_market import SteamMarketObservation
from apps.cli.refresh_market_history import (
    buff_history_days_from_db_row,
    candidate_from_market_item_row,
    compact_platform_summary,
    compact_refresh_lines,
    load_market_item_candidates,
)
from packages.contracts.observations import MarketObservationContract
from packages.domain.enums import SourceType


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


def test_refresh_market_history_prints_unicode_when_parent_encoding_is_cp1252() -> None:
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "cp1252"

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import apps.cli.refresh_market_history; print('[1/1] ★ item')",
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )

    assert result.returncode == 0
    assert "[1/1] ★ item" in result.stdout


def test_compact_refresh_lines_show_prices_errors_and_skips() -> None:
    candidates = (
        candidate_from_market_item_row(
            {
                "name": "AK-47 | Slate",
                "quality": "Field-Tested",
                "stattrak": False,
                "steam_url": "https://steamcommunity.com/market/listings/730/AK",
                "buff_url": "https://buff.163.com/goods/123",
            }
        ),
        candidate_from_market_item_row(
            {
                "name": "M4A1-S | Nitro",
                "quality": "Minimal Wear",
                "stattrak": False,
                "steam_url": "https://steamcommunity.com/market/listings/730/M4",
                "buff_url": None,
            }
        ),
    )
    results = (
        PlatformWorkerResult(
            platform_id="steam",
            observations=(
                SteamMarketObservation(
                    observation=_observation(
                        platform_id="steam",
                        market_hash_name="AK-47 | Slate (Field-Tested)",
                        price=Decimal("12.34"),
                        currency="EUR",
                    ),
                    asset_name="AK-47 | Slate",
                    category=None,
                    quality="Field-Tested",
                    variant_key="field_tested_st0",
                ),
            ),
            errors=(
                WorkerError(
                    platform_id="steam",
                    market_hash_name="M4A1-S | Nitro (Minimal Wear)",
                    message="Steam price not found: no selector contained money",
                ),
            ),
        ),
        PlatformWorkerResult(
            platform_id="buff163",
            observations=(
                Buff163Observation(
                    observation=_observation(
                        platform_id="buff163",
                        market_hash_name="AK-47 | Slate (Field-Tested)",
                        price=Decimal("86"),
                        currency="CNY",
                    ),
                    asset_name="AK-47 | Slate",
                    category=None,
                    quality="Field-Tested",
                    variant_key="field_tested_st0",
                ),
            ),
        ),
    )

    assert compact_refresh_lines(candidates, results) == (
        "[1/2] AK-47 | Slate (Field-Tested) "
        "steam=ok price=12.34 EUR buff=ok price=86 CNY",
        "[2/2] M4A1-S | Nitro (Minimal Wear) "
        "steam=error message=Steam price not found: no selector contained money buff=skip",
    )
    assert compact_platform_summary(results) == "steam_ok=1 steam_errors=1 buff_ok=1 buff_errors=0"


def test_load_market_item_candidates_filters_by_last_checked_at() -> None:
    source = getsource(load_market_item_candidates)

    assert "last_checked_at" in source


def _observation(
    *,
    platform_id: str,
    market_hash_name: str,
    price: Decimal,
    currency: str,
) -> MarketObservationContract:
    return MarketObservationContract(
        correlation_id="test",
        asset_id="asset",
        platform_id=platform_id,
        observed_at=datetime(2026, 6, 16, 12, 0, tzinfo=UTC),
        price=price,
        currency=currency,
        source_type=SourceType.SCRAPING,
        raw_payload={"market_hash_name": market_hash_name},
    )

import json
import os
from decimal import Decimal

import pytest

from apps.acquisition.platform_workers import (
    PlatformWorkerResult,
    WorkerError,
    latest_steamdt_candidates_path,
    load_steamdt_candidates,
    worker_results_to_jsonable,
)
from apps.acquisition.steam_market import SteamMarketObservation
from packages.contracts.observations import MarketObservationContract
from packages.domain.enums import SourceType


def test_load_steamdt_candidates_keeps_platform_links(tmp_path) -> None:
    path = tmp_path / "steamdt_candidates.json"
    path.write_text(
        json.dumps(
            [
                {
                    "item_name": "AK-47 | Slate",
                    "market_hash_name": "AK-47 | Slate (Field-Tested)",
                    "quality": "Field-Tested",
                    "strategy_id": "platform_arbitrage_safe",
                    "strategy_label": (
                        "Platform Balance | Buy via STEAM Buy Order | "
                        "Sell at Platform Lowest Price"
                    ),
                    "balance_type": "Platform Balance",
                    "buy_mode": "Buy via STEAM Buy Order",
                    "sell_mode": "Sell at Platform Lowest Price",
                    "buff_url": "https://buff.163.com/goods/875627",
                    "steam_url": "https://steamcommunity.com/market/listings/730/AK",
                }
            ]
        ),
        encoding="utf-8",
    )

    candidates = load_steamdt_candidates(path)

    assert candidates[0].buff_url == "https://buff.163.com/goods/875627"
    assert candidates[0].steam_url == "https://steamcommunity.com/market/listings/730/AK"
    assert candidates[0].strategy_id == "platform_arbitrage_safe"
    assert candidates[0].balance_type == "Platform Balance"
    assert candidates[0].buy_mode == "Buy via STEAM Buy Order"


def test_latest_steamdt_candidates_path_returns_newest_file(tmp_path) -> None:
    older = tmp_path / "steamdt_candidates_20260608_100000.json"
    newer = tmp_path / "steamdt_candidates_20260608_110000.json"
    ignored = tmp_path / "platform_observations_20260608_120000.json"
    older.write_text("[]", encoding="utf-8")
    newer.write_text("[]", encoding="utf-8")
    ignored.write_text("[]", encoding="utf-8")
    os.utime(older, (100, 100))
    os.utime(newer, (200, 200))

    assert latest_steamdt_candidates_path(tmp_path) == newer


def test_latest_steamdt_candidates_path_reports_missing_files(tmp_path) -> None:
    with pytest.raises(FileNotFoundError, match="no SteamDT candidate JSON found"):
        latest_steamdt_candidates_path(tmp_path)


def test_worker_results_to_jsonable_contains_observations_errors_and_summary() -> None:
    observation = MarketObservationContract(
        correlation_id="test",
        asset_id="ak_47_slate__field_tested",
        platform_id="steam",
        observed_at="2026-06-08T10:00:00+00:00",
        price=Decimal("12.34"),
        currency="EUR",
        source_type=SourceType.SCRAPING,
    )
    record = SteamMarketObservation(
        observation=observation,
        asset_name="AK-47 | Slate",
        category=None,
        quality="Field-Tested",
        variant_key="field_tested_st0",
    )

    payload = worker_results_to_jsonable(
        (
            PlatformWorkerResult(
                platform_id="steam",
                observations=(record,),
                errors=(
                    WorkerError(
                        platform_id="steam",
                        market_hash_name="bad item",
                        message="not found",
                    ),
                ),
            ),
        )
    )

    assert payload["observations"][0]["platform_id"] == "steam"
    assert payload["errors"][0]["market_hash_name"] == "bad item"
    assert payload["summary"]["steam"] == {"observations": 1, "errors": 1}

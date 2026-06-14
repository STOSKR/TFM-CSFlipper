from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest

from apps.acquisition.platform_workers import PlatformWorkerResult, WorkerError
from apps.acquisition.steam_market import SteamMarketObservation
from apps.acquisition.steamdt_hanging import SteamDTCandidate
from apps.cli.scrape_candidate_platforms import (
    build_simple_market_snapshots,
    simple_results_to_jsonable,
)
from packages.contracts.observations import MarketObservationContract
from packages.domain.enums import SourceType
from packages.persistence.simple_market import (
    SimpleMarketSnapshot,
    SimpleMarketSnapshotRepository,
)


def test_build_simple_market_snapshots_merges_platforms_by_item_variant() -> None:
    scraped_at = datetime(2026, 6, 9, 12, 0, tzinfo=UTC)
    candidate = SteamDTCandidate(
        item_name="AK-47 | Slate",
        market_hash_name="StatTrak AK-47 | Slate (Field-Tested)",
        quality="Field-Tested",
        stattrak=True,
        strategy_id="platform_arbitrage_safe",
        strategy_label="Platform Balance | Buy via STEAM Buy Order | Sell at Platform Lowest Price",
        balance_type="Platform Balance",
        buy_mode="Buy via STEAM Buy Order",
        sell_mode="Sell at Platform Lowest Price",
        steam_url="https://steamcommunity.com/market/listings/730/AK",
        buff_url="https://buff.163.com/goods/875627",
    )
    steam_record = _record(
        platform_id="steam",
        price=Decimal("17.45"),
        currency="EUR",
        market_hash_name=candidate.market_hash_name,
        source_reference=candidate.steam_url or "",
        raw_payload={
            "market_hash_name": candidate.market_hash_name,
            "recent_sales": [{"price": "17.45", "time_label": "6/13/2026, 11 PM"}],
        },
    )
    buff_record = _record(
        platform_id="buff163",
        price=Decimal("105.20"),
        currency="CNY",
        market_hash_name=candidate.market_hash_name,
        source_reference=candidate.buff_url or "",
        raw_payload={
            "market_hash_name": candidate.market_hash_name,
            "buy_orders": [{"price": "CNY 104.00", "quantity": 7}],
            "price_history": [
                {
                    "observed_at": "2026-06-13T16:00:00+00:00",
                    "buff_sell_price": "105.20",
                    "buff_buy_order_price": "104.00",
                    "buff_listing_count": 42,
                },
            ],
        },
    )

    snapshots = build_simple_market_snapshots(
        (candidate,),
        (
            PlatformWorkerResult("steam", (steam_record,)),
            PlatformWorkerResult("buff163", (buff_record,)),
        ),
        scraped_at=scraped_at,
    )

    assert len(snapshots) == 1
    snapshot = snapshots[0]
    assert snapshot.name == "AK-47 | Slate"
    assert snapshot.quality == "Field-Tested"
    assert snapshot.stattrak is True
    assert snapshot.steam_url == candidate.steam_url
    assert snapshot.buff_url == candidate.buff_url
    assert snapshot.steam_price == Decimal("17.45")
    assert snapshot.steam_currency == "EUR"
    assert snapshot.steam_recent_sales == (
        {"price": "17.45", "time_label": "6/13/2026, 11 PM"},
    )
    assert snapshot.buff_price == Decimal("105.20")
    assert snapshot.buff_currency == "CNY"
    assert snapshot.buff_buy_orders == ({"price": "CNY 104.00", "quantity": 7},)
    assert snapshot.buff_price_history == (
        {
            "observed_at": "2026-06-13T16:00:00+00:00",
            "buff_sell_price": "105.20",
            "buff_buy_order_price": "104.00",
            "buff_listing_count": 42,
        },
    )
    assert snapshot.source_strategies[0]["strategy_id"] == "platform_arbitrage_safe"


def test_simple_results_to_jsonable_uses_public_snapshot_shape() -> None:
    scraped_at = datetime(2026, 6, 9, 12, 0, tzinfo=UTC)
    snapshot = SimpleMarketSnapshot(
        name="AK-47 | Slate",
        quality="Field-Tested",
        stattrak=False,
        scraped_at=scraped_at,
        steam_url="https://steamcommunity.com/market/listings/730/AK",
        steam_price=Decimal("5.41"),
        steam_currency="EUR",
    )

    payload = simple_results_to_jsonable((snapshot,), ())

    assert payload["schema_version"] == "market_snapshot.v1"
    assert payload["items"][0]["name"] == "AK-47 | Slate"
    assert payload["items"][0]["steam"]["price"] == "5.41"
    assert "buy_orders" not in payload["items"][0]["steam"]
    assert "source_strategies" not in payload["items"][0]


def test_build_simple_market_snapshots_infers_missing_quality_from_market_hash() -> None:
    scraped_at = datetime(2026, 6, 10, 12, 0, tzinfo=UTC)
    market_hash_name = "Souvenir XM1014 | Elegant Vines (Field-Tested)"
    steam_record = _record(
        platform_id="steam",
        price=Decimal("170.47"),
        currency="CNY",
        market_hash_name=market_hash_name,
        source_reference="https://steamcommunity.com/market/listings/730/Souvenir%20XM1014",
        asset_name="Souvenir XM1014 | Elegant Vines",
        quality=None,
    )

    snapshots = build_simple_market_snapshots(
        (),
        (PlatformWorkerResult("steam", (steam_record,)),),
        scraped_at=scraped_at,
    )

    assert len(snapshots) == 1
    assert snapshots[0].name == "Souvenir XM1014 | Elegant Vines"
    assert snapshots[0].quality == "Field-Tested"


def test_build_simple_market_snapshots_skips_items_without_quality() -> None:
    scraped_at = datetime(2026, 6, 10, 12, 0, tzinfo=UTC)
    market_hash_name = "Trapper Aggressor | Guerrilla Warfare"
    steam_record = _record(
        platform_id="steam",
        price=Decimal("170.47"),
        currency="CNY",
        market_hash_name=market_hash_name,
        source_reference="https://steamcommunity.com/market/listings/730/Trapper%20Aggressor",
        asset_name=market_hash_name,
        quality=None,
    )

    snapshots = build_simple_market_snapshots(
        (),
        (PlatformWorkerResult("steam", (steam_record,)),),
        scraped_at=scraped_at,
    )

    assert snapshots == ()


def test_simple_results_to_jsonable_aggregates_summary_across_batches() -> None:
    payload = simple_results_to_jsonable(
        (),
        (
            PlatformWorkerResult("steam", (), (WorkerError("steam", "a", "bad"),)),
            PlatformWorkerResult("steam", (_record(
                platform_id="steam",
                price=Decimal("5.41"),
                currency="EUR",
                market_hash_name="AK-47 | Slate (Field-Tested)",
                source_reference="steam-url",
            ),)),
        ),
    )

    assert payload["summary"]["steam"] == {"observations": 1, "errors": 1}
    assert "debug_log" not in payload["errors"][0]


@pytest.mark.asyncio
async def test_simple_market_snapshot_repository_upserts_item_current_state() -> None:
    connection = FakeConnection()
    snapshot = SimpleMarketSnapshot(
        name="AK-47 | Slate",
        quality="Field-Tested",
        stattrak=False,
        scraped_at=datetime(2026, 6, 9, 12, 0, tzinfo=UTC),
        steam_url="https://steamcommunity.com/market/listings/730/AK",
        steam_price=Decimal("5.41"),
        steam_currency="EUR",
        steam_buy_orders=({"price": "5.00", "quantity": 12},),
    )

    await SimpleMarketSnapshotRepository(connection).record_snapshot(snapshot)

    assert len(connection.statements) == 1
    assert "insert into market_items" in connection.statements[0].lower()
    assert "steam_price" in connection.statements[0].lower()
    assert "steam_buy_orders" in connection.statements[0].lower()
    assert (
        "on conflict (name, quality, stattrak) do update set"
        in connection.statements[0].lower()
    )
    assert "scraped_at = excluded.scraped_at" in connection.statements[0].lower()
    assert connection.transaction_opened is True


@pytest.mark.asyncio
async def test_simple_market_snapshot_repository_persists_history_points() -> None:
    connection = FakeConnection()
    snapshot = SimpleMarketSnapshot(
        name="AK-47 | Slate",
        quality="Field-Tested",
        stattrak=True,
        scraped_at=datetime(2026, 6, 9, 12, 0, tzinfo=UTC),
        steam_currency="EUR",
        steam_recent_sales=(
            {
                "observed_at": "2026-06-09T10:00:00+00:00",
                "price": "17.45",
                "purchases": 3,
            },
        ),
        buff_currency="EUR",
        buff_price_history=(
            {
                "observed_at": "2026-06-09T10:00:00+00:00",
                "buff_sell_price": "15.20",
                "buff_buy_order_price": "14.80",
                "buff_listing_count": 11,
            },
        ),
    )

    await SimpleMarketSnapshotRepository(connection).record_snapshot(snapshot)

    assert len(connection.statements) == 2
    assert "insert into market_history_points" in connection.statements[1].lower()
    assert connection.args[0][3] == "AK-47 | Slate_FT_1"


def _record(
    *,
    platform_id: str,
    price: Decimal,
    currency: str,
    market_hash_name: str,
    source_reference: str,
    raw_payload: dict[str, Any] | None = None,
    asset_name: str = "AK-47 | Slate",
    quality: str | None = "Field-Tested",
) -> SteamMarketObservation:
    observation = MarketObservationContract(
        correlation_id="test",
        asset_id="ak_47_slate__field_tested__stattrak",
        platform_id=platform_id,
        observed_at=datetime(2026, 6, 9, 12, 0, tzinfo=UTC),
        price=price,
        currency=currency,
        source_type=SourceType.SCRAPING,
        source_reference=source_reference,
        raw_payload=raw_payload or {"market_hash_name": market_hash_name},
    )
    return SteamMarketObservation(
        observation=observation,
        asset_name=asset_name,
        category=None,
        quality=quality,
        variant_key="field-tested_st1",
    )


class FakeConnection:
    def __init__(self) -> None:
        self.statements: list[str] = []
        self.args: list[tuple[Any, ...]] = []
        self.transaction_opened = False

    def transaction(self) -> "FakeTransaction":
        self.transaction_opened = True
        return FakeTransaction()

    async def execute(self, query: str, *_args: Any) -> None:
        self.statements.append(query)
        self.args.append(_args)

    async def executemany(self, query: str, args: tuple[tuple[Any, ...], ...]) -> None:
        self.statements.append(query)
        self.args.append(args)

    async def fetchrow(self, query: str, *_args: Any) -> dict[str, Any]:
        self.statements.append(query)
        self.args.append(_args)
        return {"id": uuid4()}


class FakeTransaction:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *_exc_info: object) -> None:
        return None

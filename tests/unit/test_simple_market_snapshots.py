import json
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
    history_point_count,
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
                    "currency": "CNY",
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
            "currency": "CNY",
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

    assert len(connection.statements) == 2
    assert "insert into market_items" in connection.statements[0].lower()
    assert "steam_price" in connection.statements[0].lower()
    assert "steam_price_eur" in connection.statements[0].lower()
    assert "steam_price_cny" in connection.statements[0].lower()
    assert "from market_currency_rates" in connection.statements[0].lower()
    assert "latest_eur_cny.cny_per_eur" in connection.statements[0].lower()
    assert "$13::jsonb" in connection.statements[0].lower()
    assert "steam_buy_orders" in connection.statements[0].lower()
    assert "last_checked_at" in connection.statements[0].lower()
    assert (
        "on conflict (name, quality, stattrak) do update set"
        in connection.statements[0].lower()
    )
    assert "scraped_at = excluded.scraped_at" in connection.statements[0].lower()
    assert "updated_at = case" in connection.statements[0].lower()
    assert len(connection.args[0]) == 13
    assert connection.args[0][9] == '[{"price": "5.00", "quantity": 12}]'
    history_rows = connection.args[1]
    assert len(history_rows) == 1
    assert history_rows[0][1] == "steam"
    assert history_rows[0][2] == datetime(2026, 6, 9, 12, 0, tzinfo=UTC)
    assert history_rows[0][3] == "sell_price"
    assert history_rows[0][4] == Decimal("5.41")
    assert history_rows[0][5] == "EUR"
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
        buff_currency="CNY",
        buff_price_history=(
            {
                "observed_at": "2026-06-09T10:00:00+00:00",
                "currency": "CNY",
                "buff_sell_price": "15.20",
                "buff_buy_order_price": "14.80",
                "buff_listing_count": 11,
            },
        ),
    )

    await SimpleMarketSnapshotRepository(connection).record_snapshot(snapshot)

    assert len(connection.statements) == 2
    assert "insert into market_history_points" in connection.statements[1].lower()
    assert "platform_id" in connection.statements[1].lower()
    assert (
        "on conflict (item_id, platform_id, observed_at, metric_name)"
        in connection.statements[1].lower()
    )
    assert "where (" in connection.statements[1].lower()
    assert "is distinct from" in connection.statements[1].lower()
    assert "from market_currency_rates" in connection.statements[1].lower()
    assert "latest_eur_cny.cny_per_eur" in connection.statements[1].lower()
    assert connection.args[0][3] == "AK-47 | Slate_FT_1"
    history_rows = connection.args[1]
    assert len(history_rows) == 5
    assert history_rows[0][1] == "buff163"
    assert history_rows[0][3] == "buy_order_price"
    assert history_rows[0][4] == Decimal("14.80")
    assert history_rows[0][5] == "CNY"
    assert len(history_rows[0]) == 7
    assert history_rows[1][1] == "buff163"
    assert history_rows[1][3] == "listing_count"
    assert history_rows[1][4] == Decimal("11")
    assert history_rows[2][1] == "buff163"
    assert history_rows[2][3] == "sell_price"
    assert history_rows[2][4] == Decimal("15.20")
    assert history_rows[2][5] == "CNY"
    assert history_rows[3][1] == "steam"
    assert history_rows[3][3] == "sales_count"
    assert history_rows[3][4] == Decimal("3")
    assert history_rows[4][1] == "steam"
    assert history_rows[4][3] == "sell_price"
    assert history_rows[4][4] == Decimal("17.45")
    assert history_rows[4][5] == "EUR"
    assert history_point_count(snapshot) == 5


@pytest.mark.asyncio
async def test_simple_market_snapshot_repository_reports_history_points() -> None:
    connection = FakeConnection()
    snapshot = SimpleMarketSnapshot(
        name="AK-47 | Slate",
        quality="Field-Tested",
        stattrak=False,
        scraped_at=datetime(2026, 6, 9, 12, 0, tzinfo=UTC),
        buff_price=Decimal("105.20"),
        buff_currency="CNY",
    )

    report = await SimpleMarketSnapshotRepository(connection).record_snapshots_report(
        (snapshot,)
    )

    assert report.snapshots == 1
    assert report.history_points == 1


@pytest.mark.asyncio
async def test_simple_market_snapshot_repository_persists_current_buff_price_as_history() -> None:
    connection = FakeConnection()
    snapshot = SimpleMarketSnapshot(
        name="AK-47 | Slate",
        quality="Field-Tested",
        stattrak=False,
        scraped_at=datetime(2026, 6, 9, 12, 0, tzinfo=UTC),
        buff_price=Decimal("105.20"),
        buff_currency="CNY",
    )

    await SimpleMarketSnapshotRepository(connection).record_snapshot(snapshot)

    assert len(connection.statements) == 2
    history_rows = connection.args[1]
    assert len(history_rows) == 1
    assert history_rows[0][1] == "buff163"
    assert history_rows[0][2] == datetime(2026, 6, 9, 12, 0, tzinfo=UTC)
    assert history_rows[0][3] == "sell_price"
    assert history_rows[0][4] == Decimal("105.20")
    assert history_rows[0][5] == "CNY"
    assert json.loads(history_rows[0][6]) == {
        "buff163": {
            "source": "buff_current_sell_price",
            "price": "105.20",
        }
    }


@pytest.mark.asyncio
async def test_simple_market_snapshot_repository_sends_history_points_to_db_dedup() -> None:
    connection = FakeConnection()
    connection.latest_history_rows = (
        {
            "platform_id": "steam",
            "metric_name": "sell_price",
            "latest_observed_at": datetime(2026, 6, 10, 10, 0, tzinfo=UTC),
        },
        {
            "platform_id": "steam",
            "metric_name": "sales_count",
            "latest_observed_at": datetime(2026, 6, 10, 10, 0, tzinfo=UTC),
        },
    )
    snapshot = SimpleMarketSnapshot(
        name="AK-47 | Slate",
        quality="Field-Tested",
        stattrak=True,
        scraped_at=datetime(2026, 6, 11, 12, 0, tzinfo=UTC),
        steam_currency="EUR",
        steam_recent_sales=(
            {
                "observed_at": "2026-06-09T10:00:00+00:00",
                "price": "17.45",
                "purchases": 3,
            },
            {
                "observed_at": "2026-06-11T10:00:00+00:00",
                "price": "18.10",
                "purchases": 4,
            },
        ),
    )

    await SimpleMarketSnapshotRepository(connection).record_snapshot(snapshot)

    history_rows = connection.args[1]
    assert len(history_rows) == 4
    assert {row[3] for row in history_rows} == {"sell_price", "sales_count"}
    assert {row[2] for row in history_rows} == {
        datetime(2026, 6, 9, 10, 0, tzinfo=UTC),
        datetime(2026, 6, 11, 10, 0, tzinfo=UTC)
    }


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
        self.latest_history_rows: tuple[dict[str, Any], ...] = ()

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

    async def fetch(self, query: str, *_args: Any) -> tuple[dict[str, Any], ...]:
        self.statements.append(query)
        self.args.append(_args)
        return self.latest_history_rows


class FakeTransaction:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *_exc_info: object) -> None:
        return None

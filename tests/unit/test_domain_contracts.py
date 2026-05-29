from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from packages.contracts import (
    DomainEventContract,
    LegacyScrapedItemContract,
    MarketObservationContract,
    PredictionCompletedMessage,
    VoteSubmittedMessage,
)
from packages.domain import (
    DomainEventType,
    SourceType,
    VoteChoice,
    build_canonical_asset_id,
)


def test_build_canonical_asset_id_normalizes_legacy_names() -> None:
    canonical_id = build_canonical_asset_id(
        name="StatTrak™ AK-47 | Slate",
        quality="Field-Tested",
        stattrak=True,
    )

    assert canonical_id == "ak_47_slate__field_tested__stattrak"


def test_market_observation_contract_normalizes_currency() -> None:
    observation = MarketObservationContract(
        correlation_id="corr-1",
        asset_id="ak_47_slate__field_tested",
        platform_id="steam",
        observed_at=datetime(2026, 5, 29, 12, 0, tzinfo=UTC),
        price=Decimal("12.34"),
        currency="eur",
        source_type=SourceType.SCRAPING,
        volume=10,
    )

    assert observation.currency == "EUR"


def test_market_observation_contract_rejects_naive_timestamp() -> None:
    with pytest.raises(ValidationError):
        MarketObservationContract(
            correlation_id="corr-1",
            asset_id="ak_47_slate__field_tested",
            platform_id="steam",
            observed_at=datetime(2026, 5, 29, 12, 0),
            price=Decimal("12.34"),
            currency="EUR",
            source_type=SourceType.SCRAPING,
        )


def test_domain_event_contract_defaults_to_pending() -> None:
    event = DomainEventContract(
        event_type=DomainEventType.MARKET_OBSERVATION_CAPTURED,
        aggregate_id="ak_47_slate__field_tested",
        payload={"asset_id": "ak_47_slate__field_tested"},
        correlation_id="corr-1",
    )

    assert event.status.value == "pending"
    assert event.schema_version == "1.0"


def test_agent_messages_validate_probability_ranges() -> None:
    prediction = PredictionCompletedMessage(
        correlation_id="corr-1",
        prediction_id="pred-1",
        asset_id="asset-1",
        platform_id="steam",
        probability_up=Decimal("0.72"),
        expected_return=Decimal("0.13"),
        confidence=Decimal("0.81"),
        prediction_horizon="7d",
    )

    assert prediction.probability_up == Decimal("0.72")

    with pytest.raises(ValidationError):
        VoteSubmittedMessage(
            correlation_id="corr-1",
            prediction_id="pred-1",
            risk_profile_id="risk-1",
            agent_jid="agent@localhost",
            vote=VoteChoice.BUY,
            confidence=Decimal("1.2"),
            reason="too high",
        )


def test_legacy_scraped_item_contract_matches_existing_supabase_table() -> None:
    item = LegacyScrapedItemContract.model_validate(
        {
            "id": 365,
            "item_name": "MAG-7 | Monster Call",
            "quality": "Factory New",
            "stattrak": False,
            "profitability": Decimal("61.54"),
            "profit_eur": Decimal("2.19"),
            "buff_url": "https://buff.163.com/goods/781611",
            "buff_price_eur": Decimal("3.57"),
            "steam_url": "https://steamcommunity.com/market/listings/730/MAG-7",
            "steam_price_eur": Decimal("5.76"),
            "scraped_at": "2026-05-29T12:00:00",
            "source": "steamdt_hanging",
        }
    )

    assert item.scraped_at.tzinfo is not None

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from apps.cli.score_live_opportunities import _score_row
from packages.simulation.economics import default_excel_economics_config


def test_score_live_opportunity_marks_positive_spread_as_review() -> None:
    signal = _score_row(
        {
            "id": uuid4(),
            "representation_name": "AK_FT_0",
            "name": "AK",
            "quality": "Field-Tested",
            "stattrak": False,
            "scraped_at": datetime(2026, 6, 26, tzinfo=UTC),
            "steam_price_eur": Decimal("20"),
            "buff_price_eur": Decimal("15"),
            "steam_price": Decimal("20"),
            "steam_currency": "EUR",
            "buff_price": Decimal("120"),
            "buff_currency": "CNY",
        },
        economics=default_excel_economics_config(),
        correlation_id="test",
        min_profit_eur=Decimal("0"),
        min_return=Decimal("0"),
    )

    assert signal.status == "review"
    assert signal.is_signal is True
    assert signal.buy_platform == "BUFF"
    assert signal.sell_platform == "STEAM"
    assert signal.expected_profit_eur == Decimal("2.40")
    assert signal.probability_profitable == Decimal("0.99000")


def test_score_live_opportunity_blocks_missing_prices() -> None:
    signal = _score_row(
        {
            "id": uuid4(),
            "representation_name": "AK_FT_0",
            "name": "AK",
            "quality": "Field-Tested",
            "stattrak": False,
            "steam_price_eur": None,
            "buff_price_eur": Decimal("15"),
        },
        economics=default_excel_economics_config(),
        correlation_id="test",
        min_profit_eur=Decimal("0"),
        min_return=Decimal("0"),
    )

    assert signal.status == "blocked"
    assert signal.data_quality_status == "missing_data"
    assert signal.missing_fields == ("steam_price_eur",)
    assert signal.is_signal is False

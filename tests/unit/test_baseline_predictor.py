from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from packages.prediction.baseline import (
    BaselineCandidate,
    BaselinePredictionInput,
    HistoricalPricePoint,
    MomentumBaselinePredictor,
    build_baseline_features,
    prioritize_candidates,
)


def _history(*prices: str) -> tuple[HistoricalPricePoint, ...]:
    start = datetime(2026, 5, 1, tzinfo=UTC)
    return tuple(
        HistoricalPricePoint(
            observed_at=start + timedelta(days=index),
            price=Decimal(price),
            volume=10 + index,
        )
        for index, price in enumerate(prices)
    )


def test_build_baseline_features_is_deterministic() -> None:
    features = build_baseline_features(
        _history("10.00", "10.50", "11.00", "12.00", "12.50", "13.00", "13.50", "14.00")
    )

    assert features["observations"] == 8
    assert features["current_price"] == 14.0
    assert features["momentum_7d"] == pytest.approx(0.4)
    assert features["short_ma_3"] == 13.5


def test_momentum_baseline_predicts_positive_trend() -> None:
    output = MomentumBaselinePredictor().predict(
        BaselinePredictionInput(
            asset_id="ak_47_slate__field_tested",
            platform_id="steam",
            history=_history(
                "10.00",
                "10.20",
                "10.50",
                "10.90",
                "11.30",
                "11.80",
                "12.30",
                "12.90",
            ),
            correlation_id="prediction:test",
        )
    )

    assert output.prediction.model_name == "momentum_moving_average_baseline"
    assert output.prediction.probability_up > Decimal("0.50")
    assert output.prediction.expected_return > Decimal("0")
    assert output.prediction.confidence > Decimal("0.30")
    assert output.message.asset_id == "ak_47_slate__field_tested"


def test_prioritize_candidates_sorts_and_filters_by_volume() -> None:
    candidates = (
        BaselineCandidate("low", "Low", price=Decimal("1"), volume=2),
        BaselineCandidate(
            "best",
            "Best",
            price=Decimal("20"),
            volume=30,
            expected_return_hint=Decimal("0.20"),
        ),
        BaselineCandidate("ok", "Ok", price=Decimal("10"), volume=15),
    )

    ranked = prioritize_candidates(candidates, min_volume=10, limit=2)

    assert [candidate.candidate_id for candidate in ranked] == ["best", "ok"]

"""Deterministic baseline predictor for early end-to-end flows."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from packages.contracts.messages import PredictionCompletedMessage
from packages.domain.entities import Prediction

MODEL_NAME = "momentum_moving_average_baseline"
MODEL_VERSION = "0.1.0"


@dataclass(frozen=True, slots=True)
class HistoricalPricePoint:
    observed_at: datetime
    price: Decimal
    volume: int | None = None


@dataclass(frozen=True, slots=True)
class BaselinePredictionInput:
    asset_id: str
    platform_id: str
    history: tuple[HistoricalPricePoint, ...]
    prediction_horizon: str = "7d"
    correlation_id: str = "prediction:baseline"


@dataclass(frozen=True, slots=True)
class BaselineCandidate:
    candidate_id: str
    market_hash_name: str
    price: Decimal | None = None
    volume: int | None = None
    expected_return_hint: Decimal | None = None


@dataclass(frozen=True, slots=True)
class BaselinePredictionOutput:
    prediction: Prediction
    message: PredictionCompletedMessage


class MomentumBaselinePredictor:
    """Momentum and moving-average baseline, intentionally simple and deterministic."""

    def predict(self, payload: BaselinePredictionInput) -> BaselinePredictionOutput:
        points = sorted(payload.history, key=lambda point: point.observed_at)
        prices = [float(point.price) for point in points if point.price > 0]
        features = build_baseline_features(points)
        expected_return = _expected_return(features)
        probability_up = _probability_up(expected_return, features["volatility_7d"])
        confidence = _confidence(len(prices), expected_return, features["volatility_7d"])
        created_at = datetime.now(tz=UTC)
        prediction_id = str(uuid4())
        prediction = Prediction(
            prediction_id=prediction_id,
            asset_id=payload.asset_id,
            platform_id=payload.platform_id,
            probability_up=_decimal_probability(probability_up),
            expected_return=_decimal_return(expected_return),
            confidence=_decimal_probability(confidence),
            prediction_horizon=payload.prediction_horizon,
            model_name=MODEL_NAME,
            model_version=MODEL_VERSION,
            created_at=created_at,
            correlation_id=payload.correlation_id,
            features_snapshot=features,
        )
        message = PredictionCompletedMessage(
            correlation_id=payload.correlation_id,
            prediction_id=prediction_id,
            asset_id=payload.asset_id,
            platform_id=payload.platform_id,
            probability_up=prediction.probability_up,
            expected_return=prediction.expected_return,
            confidence=prediction.confidence,
            prediction_horizon=payload.prediction_horizon,
        )
        return BaselinePredictionOutput(prediction=prediction, message=message)


def build_baseline_features(points: Sequence[HistoricalPricePoint]) -> dict[str, float]:
    ordered = sorted(points, key=lambda point: point.observed_at)
    prices = [float(point.price) for point in ordered if point.price > 0]
    volumes = [float(point.volume or 0) for point in ordered]
    current = prices[-1] if prices else 0.0
    short_ma = _mean(prices[-3:])
    long_ma = _mean(prices[-7:])
    momentum_3d = _return(prices, 3)
    momentum_7d = _return(prices, 7)
    ma_signal = short_ma / long_ma - 1.0 if long_ma > 0 else 0.0
    volatility_7d = _std(_daily_returns(prices[-8:]))
    volume_trend = _return(volumes, 3)
    return {
        "observations": float(len(prices)),
        "current_price": current,
        "short_ma_3": short_ma,
        "long_ma_7": long_ma,
        "momentum_3d": momentum_3d,
        "momentum_7d": momentum_7d,
        "ma_signal": ma_signal,
        "volatility_7d": volatility_7d,
        "volume_trend_3d": volume_trend,
    }


def prioritize_candidates(
    candidates: tuple[BaselineCandidate, ...],
    *,
    min_volume: int = 0,
    limit: int | None = None,
) -> tuple[BaselineCandidate, ...]:
    filtered = [
        candidate
        for candidate in candidates
        if candidate.volume is None or candidate.volume >= min_volume
    ]
    filtered.sort(key=_candidate_score, reverse=True)
    return tuple(filtered[:limit] if limit is not None else filtered)


def _candidate_score(candidate: BaselineCandidate) -> float:
    price_score = math.log1p(float(candidate.price or Decimal("0"))) / 10
    volume_score = math.log1p(float(candidate.volume or 0)) / 10
    return_hint = float(candidate.expected_return_hint or Decimal("0"))
    return return_hint + price_score + volume_score


def _expected_return(features: dict[str, float]) -> float:
    return (
        features["momentum_7d"] * 0.50
        + features["momentum_3d"] * 0.25
        + features["ma_signal"] * 0.20
        + features["volume_trend_3d"] * 0.05
    )


def _probability_up(expected_return: float, volatility: float) -> float:
    return _clamp(0.5 + expected_return * 3.0 - volatility * 0.35, 0.05, 0.95)


def _confidence(observations: int, expected_return: float, volatility: float) -> float:
    data_confidence = min(observations / 30.0, 1.0) * 0.40
    signal_confidence = min(abs(expected_return) * 4.0, 0.25)
    volatility_penalty = min(volatility * 2.0, 0.25)
    return _clamp(0.25 + data_confidence + signal_confidence - volatility_penalty, 0.10, 0.90)


def _daily_returns(values: list[float]) -> list[float]:
    returns: list[float] = []
    for index in range(1, len(values)):
        previous = values[index - 1]
        if previous > 0:
            returns.append(values[index] / previous - 1.0)
    return returns


def _return(values: list[float], days: int) -> float:
    if len(values) <= days:
        return 0.0
    previous = values[-1 - days]
    return values[-1] / previous - 1.0 if previous > 0 else 0.0


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _std(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    avg = _mean(values)
    return math.sqrt(_mean([(value - avg) ** 2 for value in values]))


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return min(max(value, minimum), maximum)


def _decimal_probability(value: float) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.00001"))


def _decimal_return(value: float) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.00000001"))

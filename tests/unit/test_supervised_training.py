import pandas as pd

from packages.prediction.supervised_training import (
    _augment_training_frame,
    _date_aware_time_series_splits,
    _select_best_candidate,
    _sklearn,
)


def test_select_best_candidate_can_optimize_precision_at_threshold() -> None:
    reports = [
        _candidate("high_auc", roc_auc=0.80, average_precision=0.50, precision=0.70, signals=200),
        _candidate(
            "high_precision",
            roc_auc=0.70,
            average_precision=0.45,
            precision=0.90,
            signals=80,
        ),
    ]

    selected = _select_best_candidate(
        reports,
        metric="precision_at_threshold",
        threshold=0.8,
        min_signals=50,
    )

    assert selected["candidate"] == "high_precision"
    assert selected["selection_score"]["precision"] == 0.90
    assert selected["selection_score"]["signals"] == 80


def test_select_best_candidate_keeps_roc_auc_default_behavior() -> None:
    reports = [
        _candidate("high_auc", roc_auc=0.80, average_precision=0.50, precision=0.70, signals=200),
        _candidate(
            "high_precision",
            roc_auc=0.70,
            average_precision=0.45,
            precision=0.90,
            signals=80,
        ),
    ]

    selected = _select_best_candidate(
        reports,
        metric="roc_auc",
        threshold=0.8,
        min_signals=50,
    )

    assert selected["candidate"] == "high_auc"


def test_gaussian_augmentation_keeps_dates_and_labels_in_training_only() -> None:
    train = pd.DataFrame(
        {
            "observed_day": pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-03"]),
            "price": [10.0, 12.0, 14.0],
            "is_profitable": [0, 1, 1],
        }
    )

    augmented = _augment_training_frame(
        train,
        numeric_features=("price",),
        date_column="observed_day",
        augmentation="gaussian_jitter",
        ratio=1.0,
        noise_fraction=0.01,
        random_state=7,
    )

    assert len(augmented) == len(train) * 2
    assert augmented["observed_day"].isin(train["observed_day"]).all()
    assert augmented["is_profitable"].value_counts().to_dict() == {1: 4, 0: 2}


def test_date_aware_splits_do_not_separate_equal_dates() -> None:
    frame = pd.DataFrame(
        {
            "observed_day": pd.to_datetime(
                ["2026-01-01", "2026-01-01", "2026-01-02", "2026-01-02", "2026-01-03", "2026-01-03"]
            )
        }
    )

    splits = _date_aware_time_series_splits(
        _sklearn(),
        frame,
        date_column="observed_day",
        cv_splits=2,
    )

    for train_indices, validation_indices in splits:
        train_dates = set(frame.iloc[train_indices]["observed_day"])
        validation_dates = set(frame.iloc[validation_indices]["observed_day"])
        assert not train_dates.intersection(validation_dates)


def _candidate(
    name: str,
    *,
    roc_auc: float,
    average_precision: float,
    precision: float,
    signals: int,
) -> dict[str, object]:
    return {
        "candidate": name,
        "validation": {
            "roc_auc": roc_auc,
            "average_precision": average_precision,
            "brier_score": 0.2,
            "thresholds": [
                {
                    "threshold": 0.8,
                    "precision": precision,
                    "predicted_positive": signals,
                    "recall": 0.1,
                }
            ],
        },
    }

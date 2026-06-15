from packages.prediction.supervised_training import _select_best_candidate


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

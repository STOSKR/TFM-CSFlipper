"""Render the reproducible 2x2 supervised ablation used in the TFM."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


EXPERIMENTS = (
    ("Histórico\nsin aug.", "history_logistic_no_augmentation"),
    ("Sin hist.\nsin aug.", "static_no_augmentation"),
    ("Histórico\ncon jitter", "history_jitter"),
    ("Sin hist.\ncon jitter", "static_jitter"),
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Render the temporal history and augmentation ablation."
    )
    parser.add_argument(
        "--experiments-root",
        type=Path,
        default=Path("data/experiments/matrix_20260810"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("TFM/figures/experimentacion/02_ablacion_marzo.png"),
    )
    args = parser.parse_args()
    rows = [_read_metrics(args.experiments_root / directory, label) for label, directory in EXPERIMENTS]
    _render(rows, output=args.output)


def _read_metrics(path: Path, label: str) -> dict[str, float | str]:
    report = json.loads((path / "training_report.json").read_text(encoding="utf-8"))
    test = report["calibration"]["test"]
    at_085 = next(row for row in test["thresholds"] if float(row["threshold"]) == 0.85)
    return {
        "label": label,
        "auc": float(test["roc_auc"]),
        "brier": float(test["brier_score"]),
        "precision": float(at_085["precision"]),
        "signals": float(at_085["predicted_positive"]),
    }


def _render(rows: list[dict[str, float | str]], *, output: Path) -> None:
    import matplotlib.pyplot as plt  # type: ignore[import-not-found]

    labels = [str(row["label"]) for row in rows]
    colors = ["#5b9bd5", "#42bfa7", "#c9874f", "#bd6c85"]
    series = (
        ("auc", "ROC-AUC", (0.50, 0.80), True),
        ("brier", "Brier score", (0.0, 0.11), False),
        ("precision", "Precisión @ 0,85", (0.80, 1.0), True),
    )
    figure, axes = plt.subplots(1, 3, figsize=(12.0, 3.9), constrained_layout=True)
    figure.patch.set_facecolor("#fbfaf5")
    for axis, (field, title, limits, higher_is_better) in zip(axes, series, strict=True):
        values = [float(row[field]) for row in rows]
        bars = axis.bar(labels, values, color=colors, width=0.68)
        axis.set_title(title, loc="left", fontsize=10.5, fontweight="bold")
        axis.set_ylim(*limits)
        axis.set_facecolor("#fbfaf5")
        axis.grid(axis="y", color="#d9d5c8", linewidth=0.7)
        axis.set_axisbelow(True)
        axis.tick_params(axis="x", labelsize=8.2)
        for spine in ("top", "right"):
            axis.spines[spine].set_visible(False)
        for bar, value in zip(bars, values, strict=True):
            axis.text(
                bar.get_x() + bar.get_width() / 2,
                value + (0.012 if higher_is_better else 0.003),
                f"{value:.3f}",
                ha="center",
                va="bottom",
                fontsize=8.5,
                fontweight="bold",
            )
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(figure)


if __name__ == "__main__":
    main()

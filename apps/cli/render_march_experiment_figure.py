"""Render the reproducible March supervised-model comparison for the TFM."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create the March temporal-model comparison figure from saved reports."
    )
    parser.add_argument(
        "--experiments-root",
        type=Path,
        default=Path("data/experiments/walkforward_20260810"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("TFM/figures/experimentacion/01_modelos_marzo.png"),
    )
    args = parser.parse_args()

    rows = [
        _metrics(args.experiments_root, "march_logistic", "Logística\ncon histórico"),
        _metrics(args.experiments_root, "march_static", "Logística\nsin histórico"),
        _metrics(args.experiments_root, "march_random_forest", "Bosque\naleatorio"),
        _metrics(args.experiments_root, "march_with_history", "HGB\ncon histórico"),
    ]
    _render(rows, output=args.output)


def _metrics(root: Path, directory: str, label: str) -> dict[str, float | str]:
    report_path = root / directory / "training_report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    test = report["calibration"]["test"]
    return {
        "label": label,
        "auc": float(test["roc_auc"]),
        "brier": float(test["brier_score"]),
    }


def _render(rows: list[dict[str, float | str]], *, output: Path) -> None:
    import matplotlib.pyplot as plt  # type: ignore[import-not-found]

    labels = [str(row["label"]) for row in rows]
    auc = [float(row["auc"]) for row in rows]
    brier = [float(row["brier"]) for row in rows]
    colors = ["#5fd0c0", "#e8b568", "#72a6d9", "#bf879c"]
    figure, axes = plt.subplots(1, 2, figsize=(9.4, 4.1), constrained_layout=True)
    figure.patch.set_facecolor("#fbfaf5")

    for axis, values, title, ylabel in (
        (axes[0], auc, "Capacidad de separación", "ROC-AUC"),
        (axes[1], brier, "Calibración probabilística", "Brier score"),
    ):
        bars = axis.bar(labels, values, color=colors, width=0.65)
        axis.set_title(title, loc="left", fontsize=11, fontweight="bold")
        axis.set_ylabel(ylabel)
        axis.set_facecolor("#fbfaf5")
        axis.grid(axis="y", color="#d9d5c8", linewidth=0.7)
        axis.set_axisbelow(True)
        for spine in ("top", "right"):
            axis.spines[spine].set_visible(False)
        for bar, value in zip(bars, values, strict=True):
            axis.text(
                bar.get_x() + bar.get_width() / 2,
                value + (0.012 if ylabel == "ROC-AUC" else 0.0025),
                f"{value:.3f}",
                ha="center",
                va="bottom",
                fontsize=9,
                fontweight="bold",
            )
    axes[0].set_ylim(0.55, 0.82)
    axes[1].set_ylim(0.0, 0.11)
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(figure)


if __name__ == "__main__":
    main()
